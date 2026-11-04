"""Run driver: workspace -> generation (baseline or in-loop) -> hidden tests -> metrics -> summary.

Each mode (baseline, in_loop, in_loop_static) implements only `generate(ctx)`; workspace,
tests, metrics and logging are identical, so the monitor is the only difference.
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from smells.core.design_parser import Project
from smells.core.models import ChatModel, get_model
from smells.core.runlog import RunLog, git_commit, model_meta, new_run_id
from smells.core.skills import skills_fingerprint
from smells.core.workspace import prepare_workspace


@dataclass
class RunContext:
    mode: str
    project: Project
    cfg: dict
    out_dir: Path
    code_dir: Path
    log: RunLog
    llm: ChatModel
    slm: ChatModel | None
    totals: dict = field(default_factory=lambda: {
        "llm_calls": 0, "llm_tokens_in": 0, "llm_tokens_out": 0, "llm_s": 0.0,
        "slm_calls": 0, "slm_tokens_in": 0, "slm_tokens_out": 0, "slm_s": 0.0, "static_s": 0.0,
    })
    extra: dict = field(default_factory=dict)

    def write(self, path: str, code: str) -> None:
        p = self.code_dir / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code)

    def add_unit(self, ur) -> None:
        self.totals["llm_calls"] += ur.llm_calls
        self.totals["llm_tokens_in"] += ur.tokens_in
        self.totals["llm_tokens_out"] += ur.tokens_out
        self.totals["llm_s"] += ur.llm_s


def execute_run(
    mode: str,
    project: Project,
    cfg: dict,
    out_root: Path,
    generate: Callable[[RunContext], dict[str, str]],
    llm: ChatModel | None = None,
    slm: ChatModel | None = None,
    needs_slm: bool = False,
    run_tests: bool = True,
) -> Path:
    run_id = new_run_id(project.name, mode)
    out_dir = Path(out_root) / run_id
    code_dir = prepare_workspace(project, out_dir / "generated")
    log = RunLog(out_dir / "events.jsonl", run_id, project.name, mode)
    llm = llm or get_model(cfg, "codegen")
    if needs_slm and slm is None:
        slm = get_model(cfg, "judge_code")
    ctx = RunContext(mode, project, cfg, out_dir, code_dir, log, llm, slm)
    log.event(
        "run_start", models=model_meta(cfg), git_commit=git_commit(), date=dt.date.today().isoformat(),
        host=platform.node(), machine=platform.machine(), config_path=cfg.get("_config_path"),
        files_to_generate=project.source_files(), skills=skills_fingerprint(),
    )
    t0 = time.perf_counter()
    status = "ok"
    try:
        files = generate(ctx)
    except Exception as e:  # keep partial results: failures are results too
        status = f"error: {type(e).__name__}: {e}"
        log.event("error", where="generate", message=str(e)[:2000])
        files = {}
    gen_s = time.perf_counter() - t0
    summary: dict = {
        "run_id": run_id, "project": project.name, "mode": mode, "status": status,
        "date": dt.date.today().isoformat(), "git_commit": git_commit(), "models": model_meta(cfg),
        "generation_s": round(gen_s, 2), **{k: round(v, 3) if isinstance(v, float) else v for k, v in ctx.totals.items()},
        "generated_files": sorted(files), **ctx.extra,
    }
    from smells.eval.quality import quality_metrics

    summary["quality"] = quality_metrics(code_dir, project.source_files(), cfg["gates"])
    if run_tests:
        from smells.eval.tests_runner import evaluate_tests

        try:
            summary["tests"] = evaluate_tests(project, code_dir, cfg)
        except Exception as e:
            summary["tests"] = {"error": f"{type(e).__name__}: {e}"}
        log.event("tests", **{k: v for k, v in summary["tests"].items() if k != "output_tail"})
    log.event("run_end", summary={k: v for k, v in summary.items() if k not in ("quality", "tests")})
    log.close()
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return code_dir
