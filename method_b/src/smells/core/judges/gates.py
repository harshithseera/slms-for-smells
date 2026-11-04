"""Gates decide which SLM judges to run; static rules emit findings directly.

Gates keep latency and false positives down: an SLM judge is only asked about a class or
function when the static facts already suggest a possible problem.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from smells.core.schema import Finding
from smells.core.static_facts import ProjectFacts


@dataclass
class GateHit:
    judge: str  # smell id, e.g. "duplicated_logic"
    file: str
    target: str  # class or function qualname, or "a|b" for duplicate pairs
    reason: str
    facts: dict = field(default_factory=dict)


def gate(pf: ProjectFacts, path: str, g: dict) -> list[GateHit]:
    ff = pf.files[path]
    hits: list[GateHit] = []
    if ff.syntax_error:
        return hits
    hits += _duplicate_hits(pf, path)
    hits += code_smell_hits(pf, path)
    return hits


def _duplicate_hits(pf: ProjectFacts, path: str) -> list[GateHit]:
    """One judge call per cluster of mutually similar functions (its most similar pair).

    Without clustering, k near-identical functions produce k*(k-1)/2 SLM calls.
    """
    pairs = [d for d in pf.duplicates if d.a.startswith(path + "::") or d.b.startswith(path + "::")]
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for d in pairs:
        parent[find(d.a)] = find(d.b)
    clusters: dict[str, list] = {}
    for d in pairs:
        clusters.setdefault(find(d.a), []).append(d)
    hits = []
    for members in clusters.values():
        best = max(members, key=lambda d: d.similarity)
        size = len({x for d in members for x in (d.a, d.b)})
        reason = f"AST similarity {best.similarity}" + (f"; cluster of {size} similar functions" if size > 2 else "")
        hits.append(GateHit("duplicated_logic", path, f"{best.a}|{best.b}", reason, {**best.__dict__, "cluster_size": size}))
    return hits


def design_signatures(diagram) -> dict[str, int]:
    """Method/function name -> parameter count, for every operation in the UML class diagram."""
    out: dict[str, int] = {}
    if diagram is None:
        return out
    for c in diagram.classes.values():
        for m in c.methods:
            m = m.lstrip("+-#~ ")
            if "(" not in m:
                continue
            name, rest = m.split("(", 1)
            args = [a for a in rest.split(")", 1)[0].split(",") if a.strip() and a.strip() not in ("self", "cls")]
            out[name.strip()] = max(out.get(name.strip(), 0), len(args))
    return out


def static_findings(pf: ProjectFacts, path: str, g: dict, design: dict[str, int] | None = None) -> list[Finding]:
    """Smells decided by rules alone (no SLM): syntax, long method, long parameter list.

    `design` (from design_signatures) marks parameter lists that the UML fixes: those are
    reported as low, so they are logged but never fed back (changing them breaks the API).
    """
    design = design or {}
    ff = pf.files[path]
    out: list[Finding] = []
    if ff.syntax_error:
        return [Finding("syntax_error", path, "high", ff.syntax_error, "fix the syntax error", file=path)]
    for fn in ff.functions:
        if fn.loc > g["long_method_loc"] or fn.cc > g["long_method_cc"]:
            sev = "high" if fn.loc > 2 * g["long_method_loc"] or fn.cc > 2 * g["long_method_cc"] else "medium"
            out.append(
                Finding(
                    "long_method", fn.qualname, sev,
                    f"{fn.loc} lines, cyclomatic complexity {fn.cc}, nesting {fn.nesting}",
                    "extract cohesive steps into well-named helper functions", file=path,
                )
            )
        if fn.params > g["long_parameter_list"]:
            sev = "high" if fn.params > g["long_parameter_list"] + 3 else "medium"
            evidence = f"{fn.params} parameters"
            if design.get(fn.qualname.rsplit(".", 1)[-1], -1) >= fn.params:
                sev, evidence = "low", evidence + " (signature fixed by the design)"
            out.append(
                Finding(
                    "long_parameter_list", fn.qualname, sev, evidence,
                    "group related parameters into a dataclass/config object", file=path,
                )
            )
    return out


# --------------------------------------------------------------------------------------
# Gates for AST-detectable code smells judged by an SLM. Each gate only finds candidates
# cheaply; the SLM decides with that smell's skill file. Thresholds are deliberately loose.

MAGIC_OK = {0, 1, -1, 2}
DOMAIN_NAME = re.compile(r"(^|_)(email|phone|currency|iban|postcode|zip|zipcode|url|isbn|sku)(_|$)")
PRIMITIVES = {"str", "int", "float"}


def _functions(tree: ast.AST):
    """(qualname, node) for module-level functions and methods of module-level classes."""
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{m.name}", m


def _params(fn) -> list[ast.arg]:
    a = fn.args
    return [p for p in a.posonlyargs + a.args + a.kwonlyargs if p.arg not in ("self", "cls")]


def _magic_literals(fn) -> list[tuple]:
    skip: set[int] = set()
    for d in fn.args.defaults + [d for d in fn.args.kw_defaults if d is not None]:
        skip.update(id(n) for n in ast.walk(d))
    for n in ast.walk(fn):
        if isinstance(n, ast.Subscript):
            skip.update(id(x) for x in ast.walk(n.slice))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id == "range":
                skip.update(id(x) for a in n.args for x in ast.walk(a))
            elif n.func.id == "round" and len(n.args) > 1:
                skip.update(id(x) for x in ast.walk(n.args[1]))
    out = []
    for n in ast.walk(fn):
        if (isinstance(n, ast.Constant) and type(n.value) in (int, float) and id(n) not in skip
                and n.value not in MAGIC_OK):
            out.append((n.value, n.lineno))
    return sorted(set(out), key=lambda x: (x[1], x[0]))


# Methods of builtins and common stdlib value types (str, containers, files, datetime, re,
# pathlib, logging). Calling them at the END of a chain is using a value, not navigating
# through another object's internals, so they do not count as hops.
VALUE_METHODS = {
    "lower", "upper", "strip", "lstrip", "rstrip", "split", "rsplit", "join", "replace", "format",
    "startswith", "endswith", "encode", "decode", "title", "casefold", "partition", "splitlines",
    "items", "keys", "values", "get", "pop", "append", "extend", "insert", "update", "copy", "add",
    "remove", "discard", "clear", "setdefault", "sort", "index", "count",
    "read", "write", "seek", "tell", "truncate", "flush", "close", "readline", "readlines",
    "date", "time", "isoformat", "strftime", "timestamp", "astimezone", "weekday",
    "resolve", "expanduser", "absolute", "with_suffix", "joinpath", "exists", "is_file", "is_dir",
    "read_text", "write_text", "mkdir", "sub", "match", "search", "fullmatch", "findall", "group",
    "print", "debug", "info", "warning", "error", "exception",
}


VALUE_ATTRS = {"year", "month", "day", "hour", "minute", "second", "microsecond", "days", "seconds",
               "real", "imag"}


def _chain_roots(fn) -> list[ast.AST]:
    """Outermost Attribute/Call/Subscript expressions (not themselves part of a longer chain)."""
    inner = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Attribute):
            inner.add(id(n.value))
        elif isinstance(n, ast.Call):
            inner.add(id(n.func))
        elif isinstance(n, ast.Subscript):
            inner.add(id(n.value))
    return [n for n in ast.walk(fn) if isinstance(n, (ast.Attribute, ast.Call, ast.Subscript)) and id(n) not in inner]


def _imported_names(tree: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update((a.asname or a.name).split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            out.update(a.asname or a.name for a in n.names)
    return out


def _chain_hops(node: ast.AST, modules: frozenset = frozenset()) -> int:
    """Navigation hops in a chain like a.b().c[0].d: attribute steps, not counting the step
    from `self` to its own attribute nor trailing builtin/stdlib value methods (.items(),
    .lower(), .isoformat(), ...). Calls and subscripts do not break the chain."""
    attrs: list[tuple[str, bool]] = []  # (name, is_called), outermost first
    called = False
    while True:
        if isinstance(node, ast.Attribute):
            attrs.append((node.attr, called))
            called = False
            node = node.value
        elif isinstance(node, ast.Call):
            called = True
            node = node.func
        elif isinstance(node, ast.Subscript):
            called = False
            node = node.value
        else:
            break
    while attrs and ((attrs[0][1] and attrs[0][0] in VALUE_METHODS) or (not attrs[0][1] and attrs[0][0] in VALUE_ATTRS)):
        attrs.pop(0)
    hops = len(attrs)
    if isinstance(node, ast.Name) and (node.id in ("self", "cls") or node.id in modules) and hops:
        hops -= 1  # self.x is own state; module.x is a qualified name, not navigation
    return hops


def _uses_for_validation(fn, name: str) -> bool:
    """True if `name` is compared, or passed to / called on, somewhere in the body."""
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare):
            if any(isinstance(x, ast.Name) and x.id == name for x in [n.left, *n.comparators]):
                return True
        elif isinstance(n, ast.Call):
            if any(isinstance(a, ast.Name) and a.id == name for a in n.args):
                if not (isinstance(n.func, ast.Name) and n.func.id in ("str", "repr", "print")):
                    return True
            f = n.func
            while isinstance(f, (ast.Attribute, ast.Call)):
                f = f.value if isinstance(f, ast.Attribute) else f.func
            if isinstance(f, ast.Name) and f.id == name and isinstance(n.func, ast.Attribute):
                return True
    return False


def code_smell_hits(pf: ProjectFacts, path: str) -> list[GateHit]:
    src = getattr(pf, "sources", {}).get(path)
    if src is None or pf.files[path].syntax_error:
        return []
    tree = ast.parse(src)
    modules = frozenset(_imported_names(tree))
    hits: list[GateHit] = []
    for qual, fn in _functions(tree):
        lits = _magic_literals(fn)
        if lits:
            hits.append(GateHit("magic_numbers", path, qual,
                                f"numeric literals {[v for v, _ in lits]} in the function body",
                                {"literals": [{"value": v, "line": l} for v, l in lits]}))
        prim = [p.arg for p in _params(fn)
                if isinstance(p.annotation, ast.Name) and p.annotation.id in PRIMITIVES
                and DOMAIN_NAME.search(p.arg) and _uses_for_validation(fn, p.arg)]
        if prim:
            hits.append(GateHit("primitive_obsession", path, qual,
                                f"domain values passed as raw primitives and checked or transformed: {prim}",
                                {"params": prim}))
        roots = [(r, _chain_hops(r, modules)) for r in _chain_roots(fn)]
        chains = sorted({h for _, h in roots if h >= 2}, reverse=True)
        longest = [ast.unparse(r)[:120] for r, h in roots if chains and h == chains[0]]
        if chains:
            hits.append(GateHit("message_chains", path, qual,
                                f"navigates {chains[0]} objects deep", {"chains": sorted(set(longest))[:3]}))
        flags = []
        for p in _params(fn):
            is_bool = isinstance(p.annotation, ast.Name) and p.annotation.id == "bool"
            if not is_bool:
                a = fn.args
                pos = a.posonlyargs + a.args
                defaults = dict(zip([x.arg for x in pos[len(pos) - len(a.defaults):]], a.defaults))
                defaults.update({x.arg: d for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None})
                d = defaults.get(p.arg)
                is_bool = isinstance(d, ast.Constant) and isinstance(d.value, bool)
            if is_bool and any(isinstance(n, (ast.If, ast.IfExp)) and p.arg in {x.id for x in ast.walk(n.test)
                               if isinstance(x, ast.Name)} for n in ast.walk(fn)):
                flags.append(p.arg)
        if flags:
            hits.append(GateHit("flag_argument", path, qual, f"boolean parameter(s) {flags} select a branch",
                                {"flags": flags}))
    hits += _data_clump_hits(pf, path)
    return hits


def _data_clump_hits(pf: ProjectFacts, path: str, min_shared: int = 3) -> list[GateHit]:
    """The same 3+ parameter names in 2+ signatures; one hit per shared name set."""
    sigs = []
    for f, src in getattr(pf, "sources", {}).items():
        if pf.files[f].syntax_error:
            continue
        for qual, fn in _functions(ast.parse(src)):
            names = frozenset(p.arg for p in _params(fn))
            if len(names) >= min_shared:
                sigs.append((f, fn.name, fn.lineno, names))
    groups: dict[frozenset, set] = {}
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            shared = sigs[i][3] & sigs[j][3]
            if len(shared) >= min_shared:
                groups.setdefault(frozenset(shared), set()).update({sigs[i][:3], sigs[j][:3]})
    hits = []
    for shared, members in groups.items():
        members = sorted(members)
        if not any(m[0] == path for m in members):
            continue
        target = "|".join(f"{f}::{n}@{l}" for f, n, l in members[:3])
        hits.append(GateHit("data_clumps", path, target,
                            f"parameters {sorted(shared)} recur in {len(members)} signatures",
                            {"shared": sorted(shared), "functions": [f"{f}::{n}" for f, n, _ in members]}))
    return hits
