"""Deterministic, millisecond-scale facts about Python code.

Per function: LOC, cyclomatic complexity (radon), parameter count, nesting depth.
Per class: LOC, method/attribute counts, fan-out, foreign vs. self field accesses.
Project: module import graph, cycles, fan-in/fan-out, cross-function duplication.
"""
from __future__ import annotations

import ast
import builtins
import difflib
import itertools
from dataclasses import asdict, dataclass, field

from radon.complexity import cc_visit

# ------------------------------------------------------------------ data classes


@dataclass
class FunctionFacts:
    qualname: str
    file: str
    lineno: int
    loc: int
    params: int
    cc: int
    nesting: int
    self_accesses: int = 0
    foreign_accesses: dict[str, int] = field(default_factory=dict)  # receiver -> count


@dataclass
class ClassFacts:
    name: str
    file: str
    lineno: int
    loc: int
    methods: int
    attributes: int
    fan_out: int
    referenced: list[str] = field(default_factory=list)


@dataclass
class DuplicatePair:
    a: str
    b: str
    similarity: float
    lines_a: int
    lines_b: int


@dataclass
class FileFacts:
    path: str
    module: str
    loc: int
    syntax_error: str | None = None
    functions: list[FunctionFacts] = field(default_factory=list)
    classes: list[ClassFacts] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)  # absolute module names


@dataclass
class ProjectFacts:
    files: dict[str, FileFacts]
    import_graph: dict[str, list[str]]  # project-internal edges only
    cycles: list[list[str]]
    fan_in: dict[str, int]
    fan_out: dict[str, int]
    duplicates: list[DuplicatePair]

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_for(self, path: str) -> dict:
        """Compact facts for one file, to put in logs and judge prompts."""
        f = self.files[path]
        mod = f.module
        return {
            "file": path,
            "loc": f.loc,
            "syntax_error": f.syntax_error,
            "classes": [asdict(c) for c in f.classes],
            "functions": [
                {k: v for k, v in asdict(fn).items() if k != "file"} for fn in f.functions
            ],
            "imports_internal": self.import_graph.get(mod, []),
            "fan_in": self.fan_in.get(mod, 0),
            "fan_out": self.fan_out.get(mod, 0),
            "cycles": [c for c in self.cycles if mod in c],
            "duplicates": [
                asdict(d) for d in self.duplicates
                if d.a.startswith(path + "::") or d.b.startswith(path + "::")
            ],
        }


# ----------------------------------------------------------------------- helpers


def module_name(path: str) -> str:
    p = path[:-3] if path.endswith(".py") else path
    parts = [x for x in p.replace("\\", "/").split("/") if x]
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_package(path: str) -> bool:
    return path.endswith("__init__.py")


def _span(node: ast.AST) -> int:
    return (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1


def _nesting(node: ast.AST) -> int:
    blocks = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match)
    best = 0

    def walk(n: ast.AST, depth: int) -> None:
        nonlocal best
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            d = depth + 1 if isinstance(child, blocks) else depth
            best = max(best, d)
            walk(child, d)

    walk(node, 0)
    return best


def _param_count(fn: ast.FunctionDef | ast.AsyncFunctionDef, in_class: bool) -> int:
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
    if in_class and names and names[0] in ("self", "cls"):
        names = names[1:]
    return len(names) + (1 if a.vararg else 0) + (1 if a.kwarg else 0)


def _accesses(fn: ast.AST) -> tuple[int, dict[str, int]]:
    self_n, foreign = 0, {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            recv = n.value.id
            if recv in ("self", "cls"):
                self_n += 1
            else:
                foreign[recv] = foreign.get(recv, 0) + 1
    return self_n, foreign


def _resolve_imports(tree: ast.Module, module: str, is_pkg: bool) -> list[str]:
    out: list[str] = []
    pkg_parts = module.split(".") if is_pkg else module.split(".")[:-1]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = pkg_parts[: len(pkg_parts) - (n.level - 1)] if n.level > 1 else pkg_parts
                prefix = ".".join(base + ([n.module] if n.module else []))
            else:
                prefix = n.module or ""
            # "pkg.name" resolves to module pkg.name if it exists, else falls back to pkg
            out += [f"{prefix}.{a.name}" if prefix else a.name for a in n.names]
    return out


# ------------------------------------------------------------------ duplication

_NORMALIZE_KEEP = (ast.Attribute,)


class _Normalizer(ast.NodeTransformer):
    """Rename identifiers and constants so renamed copies still match."""

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="_v", ctx=node.ctx), node)

    def visit_arg(self, node):
        node.arg = "_a"
        node.annotation = None
        return node

    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(value=type(node.value).__name__), node)

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.name = "_f"
        node.decorator_list = []
        node.returns = None
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(
            getattr(node.body[0], "value", None), ast.Constant
        ):
            node.body = node.body[1:] or [ast.Pass()]
        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def _tokens(fn: ast.AST) -> list[str]:
    import copy

    norm = _Normalizer().visit(copy.deepcopy(fn))
    return [type(n).__name__ + (f":{n.attr}" if isinstance(n, ast.Attribute) else "") for n in ast.walk(norm)]


def find_duplicates(
    funcs: list[tuple[str, ast.AST]], threshold: float, min_lines: int
) -> list[DuplicatePair]:
    toks = [(name, node, _tokens(node)) for name, node in funcs if _span(node) >= min_lines]
    pairs = []
    for (na, a, ta), (nb, b, tb) in itertools.combinations(toks, 2):
        if min(len(ta), len(tb)) / max(len(ta), len(tb)) < threshold:
            continue
        sim = difflib.SequenceMatcher(None, ta, tb, autojunk=False).ratio()
        if sim >= threshold:
            pairs.append(DuplicatePair(na, nb, round(sim, 3), _span(a), _span(b)))
    return pairs


# ------------------------------------------------------------------------ main


# Names that do not count as coupling to another type: builtins, typing helpers and
# exceptions (raising or catching an error is not a design dependency).
_TYPING = {"Any", "Optional", "Union", "List", "Dict", "Set", "Tuple", "Callable", "Iterable",
           "Iterator", "Sequence", "Mapping", "TypeVar", "Generic", "Protocol", "ClassVar", "Self"}


def _is_non_coupling_name(name: str) -> bool:
    return (name in vars(builtins) or name in _TYPING
            or name.endswith(("Error", "Exception", "Warning")))


def _exception_names(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        exc = n.exc if isinstance(n, ast.Raise) else n.type if isinstance(n, ast.ExceptHandler) else None
        if exc is None:
            continue
        for x in ast.walk(exc):
            if isinstance(x, ast.Name):
                out.add(x.id)
    return out


def file_facts(path: str, code: str) -> tuple[FileFacts, ast.Module | None]:
    module = module_name(path)
    ff = FileFacts(path=path, module=module, loc=len([l for l in code.splitlines() if l.strip()]))
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        ff.syntax_error = f"line {e.lineno}: {e.msg}"
        return ff, None
    try:
        cc = {(b.lineno, b.name): b.complexity for b in cc_visit(code) if hasattr(b, "complexity")}
        for b in cc_visit(code):
            for m in getattr(b, "methods", []):
                cc[(m.lineno, m.name)] = m.complexity
    except Exception:  # radon can choke on unusual syntax; facts stay best-effort
        cc = {}

    def add_fn(fn, prefix: str, in_class: bool):
        s, f = _accesses(fn)
        ff.functions.append(
            FunctionFacts(
                qualname=f"{prefix}{fn.name}",
                file=path,
                lineno=fn.lineno,
                loc=_span(fn),
                params=_param_count(fn, in_class),
                cc=cc.get((fn.lineno, fn.name), 1),
                nesting=_nesting(fn),
                self_accesses=s,
                foreign_accesses=f,
            )
        )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_fn(node, "", False)
        elif isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            attrs = set()
            for n in ast.walk(node):
                if (
                    isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == "self"
                    and isinstance(n.ctx, ast.Store)
                ):
                    attrs.add(n.attr)
            for n in node.body:
                if isinstance(n, (ast.Assign, ast.AnnAssign)):
                    for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                        if isinstance(t, ast.Name):
                            attrs.add(t.id)
            referenced = sorted(
                {
                    n.id for n in ast.walk(node)
                    if isinstance(n, ast.Name) and n.id[:1].isupper() and n.id != node.name
                    and not _is_non_coupling_name(n.id)
                }
                - _exception_names(node)
            )
            for m in methods:
                add_fn(m, f"{node.name}.", True)
            ff.classes.append(
                ClassFacts(
                    name=node.name,
                    file=path,
                    lineno=node.lineno,
                    loc=_span(node),
                    methods=len(methods),
                    attributes=len(attrs),
                    fan_out=len(referenced),
                    referenced=referenced,
                )
            )
    ff.imports = _resolve_imports(tree, module, _is_package(path))
    return ff, tree


def _cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Strongly connected components with >1 node (or a self-loop), via Tarjan."""
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = itertools.count()

    def strong(v):
        index[v] = low[v] = next(counter)
        stack.append(v)
        on.add(v)
        for w in graph.get(v, []):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in graph.get(v, []):
                out.append(sorted(comp))

    for v in list(graph):
        if v not in index:
            strong(v)
    return out


def project_facts(files: dict[str, str], gates: dict | None = None) -> ProjectFacts:
    gates = gates or {}
    facts: dict[str, FileFacts] = {}
    funcs: list[tuple[str, ast.AST]] = []
    for path, code in files.items():
        ff, tree = file_facts(path, code)
        facts[path] = ff
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append((f"{path}::{node.name}@{node.lineno}", node))

    modules = {ff.module for ff in facts.values()}
    graph: dict[str, list[str]] = {}
    for ff in facts.values():
        targets = set()
        for imp in ff.imports:
            # map "pkg.mod.func" to the longest matching project module
            parts = imp.split(".")
            for i in range(len(parts), 0, -1):
                cand = ".".join(parts[:i])
                if cand in modules and cand != ff.module:
                    targets.add(cand)
                    break
        graph[ff.module] = sorted(targets)
    fan_in = {m: 0 for m in modules}
    for src, dsts in graph.items():
        for d in dsts:
            fan_in[d] = fan_in.get(d, 0) + 1
    fan_out = {m: len(d) for m, d in graph.items()}
    dups = find_duplicates(funcs, gates.get("dup_similarity", 0.8), gates.get("dup_min_lines", 4))
    pf = ProjectFacts(facts, graph, _cycles(graph), fan_in, fan_out, dups)
    pf.sources = dict(files)  # for AST-based gates; not part of to_dict()
    return pf
