"""In-loop smell monitoring: the LLM writes each unit, the monitor checks it, findings go back.

for each unit (dependencies first):
    LLM writes the file via write_file
    monitor: static facts -> static rules + gated SLM judges
    medium/high findings go back as the tool result; LLM revises (max_fix_rounds)
final project-wide pass on cross-file smells (cycles, cross-file duplication): 1 round
"""
from __future__ import annotations

from pathlib import Path

from smells.generation.driver import RunContext, execute_run
from smells.generation.planner import plan
from smells.core.codegen import UnitGenerator, WriteOutcome
from smells.core.design_parser import Project
from smells.core.judges.judges import SmellJudges
from smells.core.monitor import Monitor, MonitorReport, format_findings
from smells.core.schema import Finding

MODE = "in_loop"

REVISE = (
    "File written. The code-smell monitor found these problems:\n{findings}\n\n"
    "Revise `{path}` to remove them. Keep every module, class, function name, signature and "
    "behaviour required by the design documents. Call write_file with the full revised file."
)
ACCEPT_CLEAN = "File written. The smell monitor found no blocking smells. This file is done."
ACCEPT_BUDGET = "File written. Fix budget for this file is used up; it is accepted as is. This file is done."


class _Tracker:
    """Per-unit fix-round bookkeeping, including oscillation (a fix that adds a new smell)."""

    def __init__(self):
        self.seen: set[tuple[str, str]] = set()
        self.prev: set[tuple[str, str]] = set()
        self.oscillations = 0
        self.resolved = 0
        self.history: list[list[dict]] = []

    def update(self, findings: list[Finding], attempt: int) -> dict:
        keys = {f.key() for f in findings}
        new = keys - self.seen if attempt > 0 else set()
        resolved = self.prev - keys if attempt > 0 else set()
        self.oscillations += len(new)
        self.resolved += len(resolved)
        self.seen |= keys
        self.prev = keys
        self.history.append([f.to_dict() for f in findings])
        return {"new_after_fix": sorted(map(list, new)), "resolved": sorted(map(list, resolved))}


def _log_check(ctx: RunContext, rep: MonitorReport, unit: str, attempt: int, phase: str, delta: dict) -> None:
    t = ctx.totals
    t["static_s"] += rep.static_s
    t["slm_s"] += rep.slm_s
    t["slm_calls"] += rep.slm_calls
    t["slm_tokens_in"] += rep.slm_tokens_in
    t["slm_tokens_out"] += rep.slm_tokens_out
    ctx.log.event(
        "monitor_check", phase=phase, unit=unit, attempt=attempt, facts=rep.facts,
        gated_judges=[{"judge": h.judge, "target": h.target, "reason": h.reason} for h in rep.gate_hits],
        findings=[f.to_dict() for f in rep.findings], reported=[f.to_dict() for f in rep.reported],
        dropped_invalid_json=rep.invalid_dropped, judge_retries=rep.judge_retries,
        static_s=round(rep.static_s, 4), slm_latency_s=round(rep.slm_s, 3), slm_calls=rep.slm_calls,
        energy_j=None, **delta,
    )


def generate(ctx: RunContext) -> dict[str, str]:
    il = ctx.cfg["in_loop"]
    max_rounds = il["max_fix_rounds"]
    judges = SmellJudges(
        ctx.slm, ctx.project.class_diagram, enabled=il["judges"],
        json_mode=ctx.cfg["models"]["judge_code"].get("json_mode", True), options=ctx.cfg.get("judge"),
    ) if ctx.slm is not None else None
    monitor = Monitor(ctx.cfg, judges, use_slm=judges is not None, diagram=ctx.project.class_diagram)
    gen = UnitGenerator(ctx.llm, ctx.project, ctx.cfg["models"]["codegen"], ctx.log)
    written: dict[str, str] = {}
    stats = {"fix_rounds": 0, "oscillations": 0, "resolved": 0, "units_clean": 0,
             "units_budget_exhausted": 0, "invalid_json_dropped": 0, "reported_findings": 0}

    for unit in plan(ctx.project):
        path = unit.path
        tracker = _Tracker()
        state = {"clean": False}

        def on_write(code: str, attempt: int) -> WriteOutcome:
            files = {**written, path: code}
            rep = monitor.check(path, files)
            delta = tracker.update(rep.reported, attempt)
            _log_check(ctx, rep, path, attempt, "unit", delta)
            stats["invalid_json_dropped"] += rep.invalid_dropped
            stats["reported_findings"] += len(rep.reported)
            if not rep.reported:
                state["clean"] = True
                return WriteOutcome(ACCEPT_CLEAN, True)
            if attempt >= max_rounds:
                return WriteOutcome(ACCEPT_BUDGET, True)
            stats["fix_rounds"] += 1
            return WriteOutcome(REVISE.format(findings=format_findings(rep.reported), path=path), False)

        ur = gen.generate(path, written, on_write)
        ctx.add_unit(ur)
        stats["oscillations"] += tracker.oscillations
        stats["resolved"] += tracker.resolved
        stats["units_clean" if state["clean"] else "units_budget_exhausted"] += 1 if ur.code else 0
        if ur.code:
            written[path] = ur.code
            ctx.write(path, ur.code)
        ctx.log.event(
            "unit_done", unit=path, classes=unit.classes, writes=ur.writes, gave_up=ur.gave_up,
            clean=state["clean"], oscillations=tracker.oscillations, resolved=tracker.resolved,
        )

    final_pass(ctx, monitor, gen, written, stats)
    ctx.extra["in_loop"] = stats
    return written


def _cross_file(findings: list[Finding]) -> list[Finding]:
    out = []
    for f in findings:
        if f.smell == "duplicated_logic" and "|" in f.location:
            a, b = (x.strip().split("::")[0] for x in f.location.split("|", 1))
            if a != b:
                out.append(f)
    return out


def final_pass(ctx: RunContext, monitor: Monitor, gen: UnitGenerator, written: dict[str, str], stats: dict) -> None:
    """Project-wide check for cross-file smells; at most final_pass_fix_rounds rounds."""
    rounds = ctx.cfg["in_loop"].get("final_pass_fix_rounds", 1)
    for rnd in range(rounds):
        targets: dict[str, list[Finding]] = {}
        for path in list(written):
            rep = monitor.check(path, written)
            _log_check(ctx, rep, path, rnd, "final", {})
            for f in _cross_file(rep.reported):
                targets.setdefault(path, []).append(f)
        ctx.log.event("final_pass", round=rnd, files_with_findings=sorted(targets))
        if not targets:
            return
        stats["final_pass_files_revised"] = stats.get("final_pass_files_revised", 0) + len(targets)
        for path, fs in targets.items():
            others = {p: c for p, c in written.items() if p != path}
            extra = (
                f"This file was already written; a project-wide review found cross-file smells:\n"
                f"{format_findings(fs)}\n\nCurrent content of `{path}`:\n```python\n{written[path]}\n```\n"
                "Rewrite the full file to remove these smells without changing its public API."
            )
            ur = gen.generate(path, others, lambda code, i: WriteOutcome("File written. Done.", True), extra)
            ctx.add_unit(ur)
            if ur.code:
                written[path] = ur.code
                ctx.write(path, ur.code)


def run(project: Project, config: dict, out_dir: Path, llm=None, slm=None, run_tests: bool = True,
        use_slm: bool = True) -> Path:
    """use_slm=False gives the 'static rules only' ablation of the monitor."""
    if not use_slm:
        return execute_run("in_loop_static", project, config, out_dir, generate, llm=llm, run_tests=run_tests)
    return execute_run(MODE, project, config, out_dir, generate, llm=llm, slm=slm, needs_slm=True, run_tests=run_tests)
