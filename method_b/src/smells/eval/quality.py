"""Code-quality metrics on the final generated files, independent of the SLM judges.

Phase 2: pylint's design/refactoring checkers (its own implementation and default
thresholds, unrelated to our monitor) + radon maintainability index.
Phase 3: add PyExamine / DPy (not pip-installable; see docs/progress_report.md).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from radon.metrics import mi_visit

from smells.core.schema import CODE_SMELLS
from smells.core.static_facts import project_facts

# pylint message -> our smell family
PYLINT_SMELLS = {
    "too-many-arguments": "long_parameter_list",
    "too-many-positional-arguments": "long_parameter_list",
    "too-many-statements": "long_method",
    "too-many-branches": "long_method",
    "too-many-locals": "long_method",
    "too-many-nested-blocks": "long_method",
    "duplicate-code": "duplicated_logic",
}


def pylint_smells(code_dir: Path, files: list[str]) -> list[dict]:
    paths = [str(Path(code_dir) / f) for f in files if (Path(code_dir) / f).exists()]
    if not paths:
        return []
    proc = subprocess.run(
        [sys.executable, "-m", "pylint", "--output-format=json", "--disable=all",
         "--enable=" + ",".join(PYLINT_SMELLS), "--min-similarity-lines=6", "--score=n", *paths],
        cwd=code_dir, capture_output=True, text=True, timeout=300,
    )
    try:
        msgs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return [
        {"symbol": m["symbol"], "smell": PYLINT_SMELLS[m["symbol"]], "path": m["path"],
         "obj": m.get("obj", ""), "line": m.get("line")}
        for m in msgs if m.get("symbol") in PYLINT_SMELLS
    ]


def quality_metrics(code_dir: Path, files: list[str], gates: dict) -> dict:
    code = {f: (Path(code_dir) / f).read_text() for f in files if (Path(code_dir) / f).exists()}
    loc = sum(len([l for l in c.splitlines() if l.strip()]) for c in code.values())
    smells = pylint_smells(code_dir, files)
    by_family: dict[str, int] = {}
    for s in smells:
        by_family[s["smell"]] = by_family.get(s["smell"], 0) + 1
    code_s = [s for s in smells if s["smell"] in CODE_SMELLS]
    mis = []
    for c in code.values():
        try:
            mis.append(mi_visit(c, multi=True))
        except Exception:
            pass
    pf = project_facts(code, gates)
    fns = [fn for ff in pf.files.values() for fn in ff.functions]
    return {
        "files": len(code),
        "missing_files": [f for f in files if f not in code],
        "loc": loc,
        "pylint_smells": len(smells),
        "pylint_smells_by_family": by_family,
        "smell_density_per_kloc": round(1000 * len(smells) / loc, 2) if loc else None,
        "code_smells": len(code_s),
        "code_smell_density_per_kloc": round(1000 * len(code_s) / loc, 2) if loc else None,
        "pylint_details": smells,
        "maintainability_index_mean": round(sum(mis) / len(mis), 2) if mis else None,
        "syntax_errors": sum(1 for ff in pf.files.values() if ff.syntax_error),
        "functions": len(fns),
        "mean_cc": round(sum(f.cc for f in fns) / len(fns), 2) if fns else None,
        "max_cc": max((f.cc for f in fns), default=None),
        "import_cycles": len(pf.cycles),
        "internal_import_edges": sum(len(v) for v in pf.import_graph.values()),
        "duplicate_pairs": len(pf.duplicates),
    }
