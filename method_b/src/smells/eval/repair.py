"""One repair pass: scan findings -> LLM fixes each affected file once -> re-scan + tests.

Conditions:
  slm    the findings the SLM confirmed (medium/high) plus rule findings, with the SLM's
         evidence and suggested fix
  rules  every gate candidate and rule finding, unfiltered, with the gate's reason as
         evidence and the skill file's fix pattern as the suggestion

The LLM sees one file at a time with its findings; it never sees the tests. After the pass
the repaired copy is re-scanned with exactly the same pipeline, and the project's own
tests are run. Only tests that pass on the original code count (the fixed test set).
Smells that persist or are newly introduced are recorded, not fixed again.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from smells.core.judges.judges import MULTI_TARGET, _source_at
from smells.core.models import ChatModel, get_model
from smells.core.skills import skill_for
from smells.eval.scan import collect_files, scan
from smells.eval.tests_runner import _parse_junit

SYSTEM = "You are a careful senior Python engineer refactoring existing, tested code."

PROMPT = """Refactor `{path}` to remove the code smells listed below.

Rules:
- Keep the behaviour exactly the same: the project's existing tests must still pass.
- Keep every public module-level name, class and method, with the same names, parameters
  and defaults: other modules and tests depend on them. You may add private helpers
  (names starting with an underscore) in this file.
- Change only what is needed to address the findings. Leave all other code as it is.
- Do not add third-party dependencies.
- Any new helper, constant or class must be defined in this file. Only import or call names
  from other project modules if they already exist there (other files are not changed with you).
- If a finding is wrong, or cannot be fixed without changing the public interface, leave
  that code unchanged.

Findings from an automated reviewer:
{findings}
{context}
Current content of `{path}`:
```python
{code}
```

Reply with the complete new content of `{path}` in a single ```python block, and nothing else."""

CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def _locations(pred: dict) -> list[tuple[str, str, int | None]]:
    """(file, function, line) for each part of a candidate."""
    if pred["smell"] in MULTI_TARGET:
        out = []
        for part in pred["target"].split("|"):
            f, ref = part.split("::", 1)
            name, line = ref.rsplit("@", 1)
            out.append((f, name, int(line)))
        return out
    return [(pred["file"], pred["target"], None)]


def _key(pred: dict) -> tuple:
    """Identity of a finding across versions of the code (line numbers ignored)."""
    if pred["smell"] in MULTI_TARGET:
        return pred["smell"], frozenset((f, n) for f, n, _ in _locations(pred))
    return pred["smell"], pred["file"], pred["target"]


def select_findings(scan_res: dict, condition: str) -> list[dict]:
    out = []
    for p in scan_res["predictions"]:
        if condition == "slm" and not p.get("confirmed"):
            continue
        sl = p.get("slm", {})
        f = (sl.get("findings") or [{}])[0] if condition == "slm" else {}
        try:
            fix = skill_for(p["smell"]).section.split("**Fix.**", 1)[1].strip().split("\n\n")[0]
        except (KeyError, IndexError):
            fix = ""
        out.append({**p, "evidence": f.get("evidence") or p["reason"], "fix": f.get("fix") or " ".join(fix.split())})
    return out


def _findings_by_file(findings: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for f in findings:
        for file in {loc[0] for loc in _locations(f)}:
            by.setdefault(file, []).append(f)
    return by


def _public_names(code: str) -> set[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    names = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_"):
            names.add(n.name)
            if isinstance(n, ast.ClassDef):
                names |= {f"{n.name}.{m.name}" for m in n.body
                          if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_")}
    return names


def repair_file(llm: ChatModel, path: str, code: str, findings: list[dict], files: dict[str, str]) -> dict:
    lines, context = [], []
    for i, f in enumerate(findings, 1):
        where = " | ".join(f"{fl}::{n}" for fl, n, _ in _locations(f))
        lines.append(f"{i}. {f['smell']} at {where}: {f['evidence']}\n   Suggested fix: {f['fix']}")
        for fl, n, ln in _locations(f):
            if fl != path and ln is not None:
                context.append(f"Related code in `{fl}` (read-only, do not copy it here unless the fix says so):\n"
                               f"```python\n{_source_at(files.get(fl, ''), n, ln)}\n```")
    prompt = PROMPT.format(path=path, findings="\n".join(lines), code=code,
                           context=("\n" + "\n\n".join(dict.fromkeys(context)) + "\n") if context else "")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    out = {"file": path, "findings": len(findings), "latency_s": 0.0, "tokens_in": 0, "tokens_out": 0,
           "format_retries": 0}
    new, status = None, ""
    for attempt in range(2):  # one format retry for an unusable reply; still a single repair pass
        t0 = time.perf_counter()
        res = llm.chat(messages)
        out["latency_s"] = round(out["latency_s"] + time.perf_counter() - t0, 2)
        out["tokens_in"] += res.tokens_in
        out["tokens_out"] += res.tokens_out
        m = CODE_BLOCK.findall(res.text or "")
        cand = max(m, key=len).rstrip() + "\n" if m else None
        if cand is None:
            status = "no_code_block"
        else:
            try:
                ast.parse(cand)
                new, status = cand, ""
                break
            except SyntaxError as e:
                status = f"syntax_error: {e.msg} (line {e.lineno})"
        if attempt == 0:
            out["format_retries"] = 1
            messages += [{"role": "assistant", "content": res.text or ""},
                         {"role": "user", "content": f"That reply could not be used ({status}). Reply with the "
                                                     f"complete, valid Python file in one ```python block only."}]
    if new is None:
        return {**out, "status": status, "code": code}
    removed = sorted(_public_names(code) - _public_names(new))
    changed = sum(1 for a, b in zip(code.splitlines(), new.splitlines()) if a != b) + abs(
        len(code.splitlines()) - len(new.splitlines()))
    return {**out, "status": "repaired" if new != code else "unchanged", "code": new,
            "public_names_removed": removed, "lines_changed": changed}


def _module_name(path: str) -> str:
    mod = path[:-3].replace("/", ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


def _import_error(code_dir: Path, python: str, path: str) -> str | None:
    """Import the repaired module (no tests): None if it imports, else the error's last line."""
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run([python, "-c", f"import importlib; importlib.import_module({_module_name(path)!r})"],
                              cwd=code_dir, capture_output=True, text=True, timeout=120,
                              env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(code_dir), "HOME": tmp})
    if proc.returncode == 0:
        return None
    lines = [l for l in proc.stderr.strip().splitlines() if l.strip()]
    return lines[-1][:400] if lines else f"exit code {proc.returncode}"


def _import_check(llm: ChatModel, code_dir: Path, root: Path, edits: list[dict], files: dict[str, str],
                  python: str) -> None:
    """Validity check after the pass: every repaired module must import. One retry with the
    error per failing file; if it still fails, revert that file to the original. No tests."""
    for e in edits:
        e["import_ok"] = True
        if e["status"] != "repaired":
            continue
        err = _import_error(code_dir, python, e["file"])
        if err is None:
            continue
        e["import_error"] = err
        current = (code_dir / e["file"]).read_text()
        msg = (f"Importing the refactored `{e['file']}` fails with:\n{err}\n\nFix only that problem and keep "
               f"the refactoring. Names from other project modules must already exist there; define any new "
               f"helper in this file.\n\n```python\n{current}```\n\nReply with the complete file in one ```python block.")
        res = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}])
        e["import_retries"] = 1
        e["tokens_in"] += res.tokens_in
        e["tokens_out"] += res.tokens_out
        m = CODE_BLOCK.findall(res.text or "")
        fixed = max(m, key=len).rstrip() + "\n" if m else None
        ok = False
        if fixed:
            try:
                ast.parse(fixed)
                (code_dir / e["file"]).write_text(fixed)
                ok = _import_error(code_dir, python, e["file"]) is None
            except SyntaxError:
                ok = False
        if not ok:
            (code_dir / e["file"]).write_text(files[e["file"]])
            e["status"] = "reverted: does not import"
            e["import_ok"] = False
        else:
            e["lines_changed"] = sum(1 for a, b in zip(files[e["file"]].splitlines(), fixed.splitlines()) if a != b)


def run_tests(code_dir: Path, python: str, test_cmd: list[str], timeout: int = 1800) -> dict:
    with tempfile.TemporaryDirectory(prefix="smells_repair_") as tmp:
        report = Path(tmp) / "junit.xml"
        home = Path(tmp) / "home"
        home.mkdir()
        try:
            proc = subprocess.run([python, "-m", "pytest", *test_cmd, "-q", "-p", "no:cacheprovider", f"--rootdir={code_dir}",
                                   f"--junitxml={report}"], cwd=code_dir, capture_output=True, text=True,
                                  timeout=timeout, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(code_dir),
                                                        "HOME": str(home), "LANG": "en_US.UTF-8"})
            tail = proc.stdout[-1500:]
        except subprocess.TimeoutExpired:
            tail = "TIMEOUT"
        res = _parse_junit(report)
        res["passed_cases"] = _passed_cases(report)
        res["output_tail"] = tail
        return res


def _passed_cases(report: Path) -> list[str]:
    import xml.etree.ElementTree as ET
    if not report.exists():
        return []
    out = []
    for case in ET.parse(report).getroot().iter("testcase"):
        if not any(case.find(t) is not None for t in ("failure", "error", "skipped")):
            out.append(f"{case.get('classname')}::{case.get('name')}")
    return out


def repair(cfg: dict, root: Path, scan_json: Path, condition: str, out_dir: Path, python: str,
           test_cmd: list[str], include: list[str] | None = None, labels: Path | None = None,
           llm: ChatModel | None = None, slm: ChatModel | None = None, recheck: str = "static") -> dict:
    """recheck: "static" = gates/rules only (no model), "slm" = full scan, "none" = tests only."""
    root, out_dir = Path(root).absolute(), Path(out_dir).absolute()
    python = str(Path(python).absolute())  # tests run with cwd = the code copy; keep venv symlinks
    before = json.loads(Path(scan_json).read_text())
    findings = select_findings(before, condition)
    code_dir = out_dir / "code"
    if code_dir.exists():
        shutil.rmtree(code_dir)
    shutil.copytree(root, code_dir, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    files = collect_files(root)
    llm = llm or get_model(cfg, "codegen")
    t0 = time.perf_counter()
    edits = []
    for path, fs in sorted(_findings_by_file(findings).items()):
        if path not in files:
            continue
        r = repair_file(llm, path, files[path], fs, files)
        (code_dir / path).write_text(r.pop("code"))
        edits.append(r)
    _import_check(llm, code_dir, root, edits, files, python)
    repair_s = time.perf_counter() - t0

    baseline_file = out_dir.parent / f"baseline_tests_{root.name}.json"
    if baseline_file.exists():
        base_tests = json.loads(baseline_file.read_text())
    else:
        base_tests = run_tests(root, python, test_cmd)
        baseline_file.write_text(json.dumps(base_tests, indent=2))
    tests = run_tests(code_dir, python, test_cmd)
    fixed_set = set(base_tests["passed_cases"])
    still = fixed_set & set(tests["passed_cases"])

    res = {
        "codebase": str(root), "condition": condition, "scan_before": str(scan_json),
        "findings_sent": len(findings), "files_edited": len(edits),
        "edits": edits, "repair_s": round(repair_s, 1),
        "llm": {"model": getattr(llm, "name", None), "temperature": cfg["models"]["codegen"].get("temperature"),
                "calls": len(edits),
                "tokens_in": sum(e["tokens_in"] for e in edits), "tokens_out": sum(e["tokens_out"] for e in edits)},
        "tests": {"fixed_set": len(fixed_set), "still_passing": len(still),
                  "pass_rate": round(len(still) / len(fixed_set), 4) if fixed_set else None,
                  "newly_failing": sorted(fixed_set - still)[:50], "summary": {k: tests[k] for k in
                  ("tests", "passed", "failures", "errors", "skipped")}},
    }
    _write_diffs(root, code_dir, [e["file"] for e in edits], out_dir / "diffs")
    if recheck != "none":
        after = scan(cfg, code_dir, labels, use_slm=(recheck == "slm"), slm=slm, include=include,
                     out=out_dir / "scan_after.json")
        res["recheck"] = recheck
        res["smells"] = compare(before, after, findings)
        if labels:
            res["labels_after"] = after.get("scores")
    (out_dir / "repair.json").write_text(json.dumps(res, indent=2, default=str))
    return res


def _write_diffs(root: Path, code_dir: Path, files: list[str], out: Path) -> None:
    import difflib
    out.mkdir(parents=True, exist_ok=True)
    for f in files:
        a, b = (root / f).read_text().splitlines(keepends=True), (code_dir / f).read_text().splitlines(keepends=True)
        (out / (f.replace("/", "__") + ".diff")).write_text("".join(difflib.unified_diff(a, b, f"a/{f}", f"b/{f}")))


def compare(before: dict, after: dict, sent: list[dict]) -> dict:
    """Resolved / persisted / introduced, per smell, for confirmed findings and raw candidates."""
    def keys(r, confirmed_only):
        return {_key(p) for p in r["predictions"] if p.get("confirmed") or not confirmed_only}
    sent_keys = {_key(f) for f in sent}
    out = {}
    static = all(p.get("confirmed") is None for p in after["predictions"] if p["source"] == "gate")
    for view, conf in ((("candidates", False),) if static else (("confirmed", True), ("candidates", False))):
        b, a = keys(before, conf), keys(after, conf)
        per = {}
        for smell in sorted({k[0] for k in b | a}):
            bs, as_ = {k for k in b if k[0] == smell}, {k for k in a if k[0] == smell}
            per[smell] = {"before": len(bs), "after": len(as_), "resolved": len(bs - as_),
                          "persisted": len(bs & as_), "introduced": len(as_ - bs)}
        per["_total"] = {"before": len(b), "after": len(a), "resolved": len(b - a),
                         "persisted": len(b & a), "introduced": len(a - b)}
        out[view] = per
    a_conf = keys(after, not static)
    out["sent_resolved"] = len(sent_keys - a_conf)
    out["sent_total"] = len(sent_keys)
    return out


def format_repair(res: dict) -> str:
    t = res["tests"]
    lines = [f"Repair ({res['condition']}) of {res['codebase']}: {res['findings_sent']} findings sent, "
             f"{res['files_edited']} files edited by {res['llm']['model']} in {res['repair_s']}s",
             f"Tests: {t['still_passing']}/{t['fixed_set']} of the original passing tests still pass "
             f"({t['pass_rate']:.1%})" if t["pass_rate"] is not None else "Tests: no baseline"]
    st = {}
    for e in res["edits"]:
        st[e["status"].split(":")[0]] = st.get(e["status"].split(":")[0], 0) + 1
    lines.append(f"Edit outcomes: {st}; public names removed in "
                 f"{sum(1 for e in res['edits'] if e.get('public_names_removed'))} files")
    if "smells" in res:
        s = res["smells"]
        view = "confirmed" if "confirmed" in s else "candidates"
        lines += [f"Findings sent that the {res.get('recheck')} re-check no longer flags: "
                  f"{s['sent_resolved']}/{s['sent_total']}",
                  "", f"| smell | {view} before | after | gone | still flagged | newly flagged |", "|---|---|---|---|---|---|"]
        for smell, v in s[view].items():
            lines.append(f"| {smell} | {v['before']} | {v['after']} | {v['resolved']} | {v['persisted']} | {v['introduced']} |")
    return "\n".join(lines)


def attribute(run_dir: Path, root: Path, python: str, test_cmd: list[str]) -> dict:
    """Apply each repaired file ON ITS OWN to the original code and run the fixed test set:
    which file's repair breaks which tests (one bad file otherwise zeroes a whole suite)."""
    run_dir, root = Path(run_dir).absolute(), Path(root).absolute()
    python = str(Path(python).absolute())
    rep = json.loads((run_dir / "repair.json").read_text())
    base = json.loads((run_dir.parent / f"baseline_tests_{root.name}.json").read_text())
    fixed = set(base["passed_cases"])
    rows = []
    for e in rep["edits"]:
        if e["status"] != "repaired":
            continue
        with tempfile.TemporaryDirectory(prefix="smells_attr_") as tmp:
            work = Path(tmp).resolve() / root.name  # /var -> /private/var on macOS: keep test ids stable
            shutil.copytree(root, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
            shutil.copy(run_dir / "code" / e["file"], work / e["file"])
            t = run_tests(work, python, test_cmd)
        broken = sorted(fixed - set(t["passed_cases"]))
        rows.append({"file": e["file"], "findings": e["findings"], "still_passing": len(fixed) - len(broken),
                     "broken": len(broken), "loads": t["tests"] > 0, "examples": broken[:5]})
    res = {"run": str(run_dir), "fixed_set": len(fixed), "files": rows,
           "files_safe": sum(r["broken"] == 0 for r in rows), "files_breaking": sum(r["broken"] > 0 for r in rows)}
    (run_dir / "attribution.json").write_text(json.dumps(res, indent=2))
    return res
