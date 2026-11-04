"""CLI: `smells run|compare|detect|reference`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from smells.core.design_parser import list_projects, load_project
from smells.config import load_config, resolve_path

MODES = ("baseline", "in_loop", "in_loop_static")  # baseline = single pass, the reference for in-loop


def _run_mode(mode: str, project, cfg: dict, out: Path, run_tests: bool) -> Path:
    if mode == "baseline":
        from smells.generation.baseline import run
    elif mode in ("in_loop", "in_loop_static"):
        from smells.generation.in_loop import run

        return run(project, cfg, out, run_tests=run_tests, use_slm=mode == "in_loop")
    return run(project, cfg, out, run_tests=run_tests)


def cmd_run(a) -> None:
    cfg = load_config(a.config)
    projects_dir = resolve_path(cfg, "projects")
    projects = list_projects(projects_dir) if a.project == ["all"] else a.project
    out = Path(a.out) if a.out else resolve_path(cfg, "runs")
    for name in projects:
        for mode in a.mode:
            for _ in range(a.repeats):
                print(f"[{mode}] {name} ...", flush=True)
                code_dir = _run_mode(mode, load_project(projects_dir, name), cfg, out, not a.no_tests)
                s = json.loads((code_dir.parent / "summary.json").read_text())
                t = s.get("tests", {})
                q = s["quality"]
                print(f"  -> {code_dir.parent.name}: status={s['status']} pass_rate={t.get('pass_rate')} "
                      f"pylint_smells={q['pylint_smells']} density/kloc={q['smell_density_per_kloc']} "
                      f"gen_s={s['generation_s']}", flush=True)


def load_summaries(runs_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(Path(runs_dir).glob("*/summary.json"))]


def cmd_compare(a) -> None:
    rows = load_summaries(Path(a.runs_dir))
    cols = ["project", "mode", "status", "pass", "tests", "loc", "code/kloc", "MI", "cycles", "dups",
            "fix_rnds", "oscill", "llm_tok", "slm_calls", "gen_s"]
    table = []
    for s in rows:
        t, q, il = s.get("tests", {}), s["quality"], s.get("in_loop", {})
        table.append([
            s["project"], s.get("mode", s.get("mode")), s["status"][:10], t.get("pass_rate"), f"{t.get('passed')}/{t.get('reference_tests')}",
            q["loc"], q.get("code_smell_density_per_kloc"),
            q["maintainability_index_mean"],
            q["import_cycles"], q["duplicate_pairs"], il.get("fix_rounds", "-"), il.get("oscillations", "-"),
            s["llm_tokens_in"] + s["llm_tokens_out"], s["slm_calls"], s["generation_s"],
        ])
    if a.markdown:
        print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
        for r in table:
            print("| " + " | ".join(str(x) for x in r) + " |")
    else:
        w = [max(len(str(x)) for x in [c, *(r[i] for r in table)]) for i, c in enumerate(cols)]
        print("  ".join(c.ljust(w[i]) for i, c in enumerate(cols)))
        for r in table:
            print("  ".join(str(x).ljust(w[i]) for i, x in enumerate(r)))


def cmd_detect(a) -> None:
    from smells.eval.detection import run_detection

    cfg = load_config(a.config)
    res = run_detection(cfg, use_slm=not a.static_only, out=Path(a.out) if a.out else None)
    print(json.dumps(res["metrics"], indent=2))


def cmd_reference(a) -> None:
    """Run hidden tests on the reference implementations (sanity check of the test env)."""
    from smells.eval.tests_runner import run_tests

    cfg = load_config(a.config)
    projects_dir = resolve_path(cfg, "projects")
    for name in a.project:
        p = load_project(projects_dir, name)
        r = run_tests(p, p.root, cfg)
        print(f"{name}: {r['passed']}/{r['tests']} passed (rc={r['returncode']})")


def check_models(cfg: dict, get=None) -> bool:
    """One tiny request per model: endpoint, key, model name, tool calling, JSON mode."""
    from smells.core.codegen import WRITE_FILE_TOOL
    from smells.core.models import get_model

    get = get or get_model
    ok = True
    probes = {
        "codegen": dict(messages=[{"role": "user", "content": "Call write_file with path 'a.py' and content 'x = 1'."}],
                        tools=[WRITE_FILE_TOOL] if cfg["models"]["codegen"].get("use_tools", True) else None),
        "judge_code": dict(messages=[{"role": "user", "content": 'Reply with the JSON {"findings": []} and nothing else.'}],
                           json_mode=cfg["models"]["judge_code"].get("json_mode", True)),
    }
    for role, kw in probes.items():
        name = cfg["models"][role].get("model")
        try:
            r = get(cfg, role).chat(**kw)
        except Exception as e:  # noqa: BLE001 - report any failure
            print(f"FAIL {role} ({name}): {type(e).__name__}: {str(e)[:300]}")
            ok = False
            continue
        if role == "codegen" and kw["tools"]:
            good = any(c.name == "write_file" for c in r.tool_calls)
            note = "tool call ok" if good else "no write_file tool call (set use_tools: false to use fenced code)"
        elif role == "judge_code":
            from smells.core.judges.judges import _load_json  # same extraction as the real parser
            try:
                good = isinstance(_load_json(r.text).get("findings"), list)
            except (ValueError, AttributeError):
                good = False
            note = "valid JSON" if good else f"invalid JSON: {r.text[:120]!r}"
        else:
            good, note = bool(r.text), "text ok"
        ok &= good
        print(f"{'ok  ' if good else 'WARN'} {role} ({r.model or name}): {note}, {r.latency_s:.1f}s, "
              f"{r.tokens_in}+{r.tokens_out} tokens")
    ok &= _check_judge_context(cfg, get)
    return ok


def _check_judge_context(cfg: dict, get) -> bool:
    """Judge prompts are ~2-4k tokens. Ollama silently drops the START of a prompt that
    exceeds its context window, i.e. the skill rules. Detect that from the token count."""
    from smells.core.skills import skill_for

    filler = "\n".join(f"    def m{i}(self, x):\n        return self.v{i} + x" for i in range(400))  # ~4.5k tokens: a judge prompt with a large class
    prompt = (skill_for("duplicated_logic").prompt_text() + "\n\n## Your task\nCode:\n```python\nclass Big:\n"
              + filler + '\n```\nReply {"findings": []}.')
    expected = len(prompt) // 4  # rough chars-per-token estimate
    try:
        r = get(cfg, "judge_code").chat([{"role": "user", "content": prompt}],
                                        json_mode=cfg["models"]["judge_code"].get("json_mode", True))
    except Exception as e:  # noqa: BLE001
        print(f"FAIL judge context probe: {type(e).__name__}: {str(e)[:200]}")
        return False
    if not r.tokens_in:
        print("WARN judge context: server reported no token usage; cannot detect truncation")
        return True
    if r.tokens_in < 0.75 * expected:
        print(f"FAIL judge context: ~{expected} prompt tokens sent, {r.tokens_in} processed -> prompts are "
              "truncated. Raise the context window (Ollama: OLLAMA_CONTEXT_LENGTH=8192 when starting the server).")
        return False
    print(f"ok   judge context: {r.tokens_in} prompt tokens processed (~{expected} sent), no truncation")
    return True


def _with_temperature(cfg: dict, role: str, t: float | None) -> dict:
    if t is not None:
        cfg["models"][role]["temperature"] = t
    return cfg


def cmd_scan(a) -> None:
    from smells.eval.scan import format_report, scan

    res = scan(_with_temperature(load_config(a.config), "judge_code", a.temperature), Path(a.path), Path(a.labels) if a.labels else None,
               use_slm=not a.static_only, out=Path(a.out) if a.out else None, include=a.include,
               max_per_smell=a.max_per_smell, seed=a.seed, review_csv=Path(a.review_csv) if a.review_csv else None)
    print(format_report(res))
    if a.out:
        print(f"\nfull results: {a.out}")
    if a.review_csv:
        print(f"review sheet: {a.review_csv}")


def cmd_repair(a) -> None:
    import shlex

    from smells.eval.repair import format_repair, repair

    res = repair(_with_temperature(load_config(a.config), "codegen", a.temperature), Path(a.path), Path(a.scan), a.condition, Path(a.out), a.python,
                 shlex.split(a.test_args), include=a.include, labels=Path(a.labels) if a.labels else None,
                 recheck=a.recheck)
    print(format_repair(res))
    print(f"\nfull results: {Path(a.out) / 'repair.json'}")


def cmd_stats(a) -> None:
    from smells.eval.report_stats import write

    d = write(Path(a.out) if a.out else None)
    print(f"{len(d['scans'])} scans, {len(d['repairs'])} repair runs -> {a.out or 'results/report_stats.md'}")


def cmd_check(a) -> None:
    raise SystemExit(0 if check_models(load_config(a.config)) else 1)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="smells")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="generate code from design project(s): baseline and/or in-loop")
    r.add_argument("--mode", nargs="+", choices=MODES, required=True)
    r.add_argument("--project", nargs="+", required=True, help="project names or 'all'")
    r.add_argument("--config", default=None)
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--out", default=None)
    r.add_argument("--no-tests", action="store_true")
    r.set_defaults(fn=cmd_run)
    c = sub.add_parser("compare", help="summary table of runs")
    c.add_argument("runs_dir", nargs="?", default="results/runs")
    c.add_argument("--markdown", action="store_true")
    c.set_defaults(fn=cmd_compare)
    d = sub.add_parser("detect", help="detection precision/recall on seeded snippets")
    d.add_argument("--config", default=None)
    d.add_argument("--static-only", action="store_true")
    d.add_argument("--out", default=None)
    d.set_defaults(fn=cmd_detect)
    f = sub.add_parser("reference", help="run hidden tests on reference code")
    f.add_argument("--project", nargs="+", required=True)
    f.add_argument("--config", default=None)
    f.set_defaults(fn=cmd_reference)
    sc = sub.add_parser("scan", help="detect smells in an existing codebase (optionally score vs labels)")
    sc.add_argument("path", help="codebase root (tests and unit_tests/ are skipped)")
    sc.add_argument("--labels", default=None, help="ground-truth labels.yaml to score against")
    sc.add_argument("--config", default=None)
    sc.add_argument("--static-only", action="store_true", help="rules only, no SLM calls")
    sc.add_argument("--out", default=None, help="write full JSON results here")
    sc.add_argument("--include", nargs="+", default=None, help="only scan these subfolders (relative to path)")
    sc.add_argument("--max-per-smell", type=int, default=None, help="randomly sample at most N candidates per smell")
    sc.add_argument("--seed", type=int, default=0, help="sampling seed")
    sc.add_argument("--review-csv", default=None, help="write a spot-check sheet (code + SLM verdict) here")
    sc.add_argument("--temperature", type=float, default=None, help="override the SLM judge's temperature")
    sc.set_defaults(fn=cmd_scan)
    rp = sub.add_parser("repair", help="one LLM repair pass from scan findings, then re-scan + tests")
    rp.add_argument("path", help="codebase root (as scanned)")
    rp.add_argument("--scan", required=True, help="scan JSON with the findings (from smells scan --out)")
    rp.add_argument("--condition", choices=["slm", "rules"], default="slm",
                    help="slm = SLM-confirmed findings; rules = every gate candidate, unfiltered")
    rp.add_argument("--out", required=True, help="output dir (repaired copy, scan_after.json, repair.json)")
    rp.add_argument("--python", required=True, help="interpreter with the project's test dependencies")
    rp.add_argument("--test-args", required=True, help='pytest arguments, e.g. "unit_tests"')
    rp.add_argument("--include", nargs="+", default=None)
    rp.add_argument("--labels", default=None)
    rp.add_argument("--config", default=None)
    rp.add_argument("--temperature", type=float, default=None, help="override the repair LLM's temperature")
    rp.add_argument("--recheck", choices=["static", "slm", "none"], default="static",
                    help="after repair: static = gates/rules only (default), slm = full SLM scan, none = tests only")
    rp.set_defaults(fn=cmd_repair)
    stp = sub.add_parser("stats", help="collect report-ready statistics from all results into one Markdown file")
    stp.add_argument("--out", default=None)
    stp.set_defaults(fn=cmd_stats)
    k = sub.add_parser("check", help="ping the configured models before a real run")
    k.add_argument("--config", default=None)
    k.set_defaults(fn=cmd_check)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main(sys.argv[1:])
