"""Baseline mode: LLM + design docs, single pass, no feedback (the reference for in-loop).

Uses the same unit-by-unit generator, prompts and unit order as in-loop monitoring, so the
only difference between the two is the monitor.
"""
from __future__ import annotations

from pathlib import Path

from smells.generation.driver import RunContext, execute_run
from smells.core.codegen import UnitGenerator, WriteOutcome
from smells.core.design_parser import Project

MODE = "baseline"


def generate(ctx: RunContext) -> dict[str, str]:
    gen = UnitGenerator(ctx.llm, ctx.project, ctx.cfg["models"]["codegen"], ctx.log)
    written: dict[str, str] = {}
    for path in ctx.project.source_files():
        ur = gen.generate(path, written, lambda code, i: WriteOutcome("File written.", accept=True))
        ctx.add_unit(ur)
        if ur.code:
            written[path] = ur.code
            ctx.write(path, ur.code)
        ctx.log.event("unit_done", unit=path, writes=ur.writes, gave_up=ur.gave_up, llm_calls=ur.llm_calls)
    return written


def run(project: Project, config: dict, out_dir: Path, llm=None, slm=None, run_tests: bool = True) -> Path:
    return execute_run(MODE, project, config, out_dir, generate, llm=llm, run_tests=run_tests)
