"""Detection quality on seeded snippets: static rules alone vs. rules + SLM judge.

Snippet-level per-smell precision/recall. "rules" predicts a smell whenever its gate
fires; "rules+slm" predicts it only when the SLM judge confirms the gated candidate.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from smells.core.judges.gates import gate
from smells.core.judges.judges import SLM_JUDGES, SmellJudges
from smells.core.models import ChatModel, get_model
from smells.core.static_facts import project_facts
from smells.config import REPO_ROOT

SEEDED = REPO_ROOT / "data" / "seeded"


def _prf(pred: dict[str, set], gold: dict[str, set], smell: str) -> dict:
    tp = sum(1 for k in gold if smell in pred[k] and smell in gold[k])
    fp = sum(1 for k in gold if smell in pred[k] and smell not in gold[k])
    fn = sum(1 for k in gold if smell not in pred[k] and smell in gold[k])
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def run_detection(cfg: dict, use_slm: bool = True, slm: ChatModel | None = None, out: Path | None = None,
                  seeded_dir: Path = SEEDED) -> dict:
    labels = yaml.safe_load((seeded_dir / "labels.yaml").read_text())
    labelled = {s for lab in labels.values() for s in [*lab.get("smells", []), lab.get("hard_negative")] if s}
    scope = [s for s in SLM_JUDGES if s in cfg["in_loop"]["judges"] and s in labelled]
    judges = None
    if use_slm:
        slm = slm or get_model(cfg, "judge_code")
        judges = SmellJudges(slm, None, enabled=scope,
                             json_mode=cfg["models"]["judge_code"].get("json_mode", True), options=cfg.get("judge"))
    gold, rules, slm_pred, details = {}, {}, {}, []
    latencies, invalid = [], 0
    for name, lab in labels.items():
        code = (seeded_dir / "snippets" / name).read_text()
        files = {name: code}
        pf = project_facts(files, cfg["gates"])
        hits = [h for h in gate(pf, name, cfg["gates"]) if h.judge in scope]
        gold[name] = set(lab["smells"])
        rules[name] = {h.judge for h in hits}
        slm_pred[name] = set()
        rec = {"snippet": name, "gold": sorted(gold[name]), "gate_hits": [[h.judge, h.target] for h in hits]}
        if judges:
            rec["slm"] = []
            for h in hits:
                t0 = time.perf_counter()
                jr = judges.judge(h, files)
                latencies.append(time.perf_counter() - t0)
                invalid += jr.invalid_dropped
                if jr.findings:
                    slm_pred[name].add(h.judge)
                rec["slm"].append({"judge": h.judge, "target": h.target, "findings": [f.to_dict() for f in jr.findings],
                                   "invalid": jr.invalid_dropped, "retries": jr.retries})
        details.append(rec)
    metrics = {"n_snippets": len(labels), "scope": scope, "rules": {s: _prf(rules, gold, s) for s in scope}}
    if judges:
        metrics["rules+slm"] = {s: _prf(slm_pred, gold, s) for s in scope}
        metrics["slm_model"] = slm.name
        metrics["slm_calls"] = len(latencies)
        metrics["slm_latency_mean_s"] = round(sum(latencies) / len(latencies), 2) if latencies else None
        metrics["slm_latency_max_s"] = round(max(latencies), 2) if latencies else None
        metrics["invalid_json_dropped"] = invalid
    res = {"metrics": metrics, "details": details}
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(res, indent=2, default=str))
    return res
