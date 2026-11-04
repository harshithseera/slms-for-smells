"""Run DevBench's hidden unit tests against a generated project.

Tests are copied in only here, into a throwaway copy, after generation has finished.
Pass rate = passed test cases / test cases collected on the *reference* implementation,
so an import error that hides tests still counts them as failed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from smells.core.design_parser import Project
from smells.config import REPO_ROOT

VENVS = REPO_ROOT / ".venvs"
REF_CACHE = REPO_ROOT / "results" / "reference_tests.json"


def _requirements(project: Project) -> Path | None:
    for c in (project.root / "requirements.txt", project.root / "docs" / "requirements.txt"):
        if c.is_file() and c.read_text().strip():
            return c
    return None


def project_python(project: Project, cfg: dict) -> str:
    """Interpreter with the project's requirements + pytest (cached venv per project)."""
    if cfg.get("eval", {}).get("python"):
        return cfg["eval"]["python"]
    venv = VENVS / project.name
    py = venv / "bin" / "python"
    marker = venv / ".ready"
    if not marker.exists():
        uv = shutil.which("uv")
        if uv:
            subprocess.run([uv, "venv", "-q", "-p", f"{sys.version_info.major}.{sys.version_info.minor}", str(venv)], check=True)
            cmd = [uv, "pip", "install", "-q", "-p", str(py), "pytest"]
        else:
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
            cmd = [str(py), "-m", "pip", "install", "-q", "pytest"]
        req = _requirements(project)
        if req:
            cmd += ["-r", str(req)]
        subprocess.run(cmd, check=True)
        marker.write_text("ok")
    return str(py)


def _parse_junit(path: Path) -> dict:
    if not path.exists():
        return {"tests": 0, "passed": 0, "failures": 0, "errors": 0, "skipped": 0, "failed_cases": []}
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    t = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    failed = []
    for s in suites:
        for k in t:
            t[k] += int(s.get(k, 0))
        for case in s.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                failed.append(f"{case.get('classname')}::{case.get('name')}")
    t["passed"] = t["tests"] - t["failures"] - t["errors"] - t["skipped"]
    t["failed_cases"] = failed
    return t


def run_tests(project: Project, code_dir: Path, cfg: dict) -> dict:
    py = project_python(project, cfg)
    tests_src = project.root / project.unit_tests_dir
    with tempfile.TemporaryDirectory(prefix=f"smells_{project.name}_") as tmp:
        work = Path(tmp) / project.name
        shutil.copytree(code_dir, work)
        shutil.copytree(tests_src, work / project.unit_tests_dir, dirs_exist_ok=True)
        report = Path(tmp) / "junit.xml"
        try:
            proc = subprocess.run(
                [py, "-m", "pytest", project.unit_tests_dir, "-q", "-p", "no:cacheprovider",
                 f"--junitxml={report}", "-o", "addopts="],
                cwd=work, capture_output=True, text=True,
                timeout=cfg.get("eval", {}).get("test_timeout_s", 300),
                env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(work), "HOME": tmp},
            )
            out, rc = proc.stdout[-4000:], proc.returncode
        except subprocess.TimeoutExpired:
            out, rc = "TIMEOUT", -1
        res = _parse_junit(report)
    res["returncode"] = rc
    res["output_tail"] = out[-1500:]
    return res


def reference_test_count(project: Project, cfg: dict) -> int:
    cache = json.loads(REF_CACHE.read_text()) if REF_CACHE.exists() else {}
    if project.name not in cache:
        r = run_tests(project, project.root, cfg)
        cache[project.name] = {"tests": r["tests"], "passed": r["passed"]}
        REF_CACHE.parent.mkdir(parents=True, exist_ok=True)
        REF_CACHE.write_text(json.dumps(cache, indent=2))
    return cache[project.name]["tests"]


def evaluate_tests(project: Project, code_dir: Path, cfg: dict) -> dict:
    r = run_tests(project, code_dir, cfg)
    ref = reference_test_count(project, cfg)
    r["reference_tests"] = ref
    r["pass_rate"] = round(r["passed"] / ref, 4) if ref else None
    return r
