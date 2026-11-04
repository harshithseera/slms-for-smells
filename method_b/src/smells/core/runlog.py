"""JSONL run log, one event format for every mode (baseline, in_loop, in_loop_static).

Each line: {"ts", "run_id", "project", "mode", "event", ...event fields}
Events: run_start, llm_call, monitor_check, unit_done, final_pass, tests, run_end.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from smells.config import REPO_ROOT


def git_commit() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def _default(o: Any):
    if is_dataclass(o):
        return asdict(o)
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)


def new_run_id(project: str, mode: str) -> str:
    return f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}_{mode}_{project}"


class RunLog:
    def __init__(self, path: Path, run_id: str, project: str, mode: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.base = {"run_id": run_id, "project": project, "mode": mode}
        self._fh = self.path.open("a", encoding="utf-8")

    def event(self, event: str, **fields: Any) -> None:
        rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), **self.base, "event": event, **fields}
        self._fh.write(json.dumps(rec, default=_default) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def read_events(path: Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def model_meta(cfg: dict) -> dict:
    return {
        role: {k: m.get(k) for k in ("model", "base_url", "temperature", "seed", "quantization")}
        for role, m in cfg["models"].items()
    }
