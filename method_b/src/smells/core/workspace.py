"""Workspace for one run: the DevBench reference repo minus the files to generate and tests.

Convention (DevBench implementation task): files in code_file_DAG are generated; the rest
of the repository (package __init__ files, resources, templates) is the given scaffold.
Unit and acceptance tests are removed so neither generator nor judges can see them.
"""
from __future__ import annotations

import ast
import shutil
from pathlib import Path

from smells.core.design_parser import Project

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache"}


def prepare_workspace(project: Project, dest: Path) -> Path:
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    hidden = {project.unit_tests_dir, project.config.get("acceptance_tests", "acceptance_tests"), "unit_tests"}
    to_generate = set(project.source_files())

    def ignore(dirpath: str, names: list[str]) -> set[str]:
        rel = Path(dirpath).relative_to(project.root)
        out = set()
        for n in names:
            relp = (rel / n).as_posix().lstrip("./") if str(rel) != "." else n
            if n in EXCLUDE_DIRS or relp in hidden or relp in to_generate:
                out.add(n)
        return out

    shutil.copytree(project.root, dest, ignore=ignore)
    # make sure every generated file's package directory is importable
    for f in to_generate:
        parts = Path(f).parts[:-1]
        for i in range(1, len(parts) + 1):
            d = dest.joinpath(*parts[:i])
            if parts[0] == "src" and i == 1:
                continue
            d.mkdir(parents=True, exist_ok=True)
            init = d / "__init__.py"
            if not init.exists() and init.relative_to(dest).as_posix() not in to_generate:
                init.write_text("")
    return dest


def summarize_code(path: str, code: str) -> str:
    """Short summary of a written file for the generator's context: signatures only."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"{path}: (syntax error at line {e.lineno})"
    lines = [f"{path}:"]
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            lines.append("  " + ast.unparse(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(f"  def {node.name}({ast.unparse(node.args)})")
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            lines.append(f"  class {node.name}({bases}):")
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines.append(f"    def {m.name}({ast.unparse(m.args)})")
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
            lines.append("  " + ", ".join(t.id for t in node.targets) + " = ...")
    return "\n".join(lines)
