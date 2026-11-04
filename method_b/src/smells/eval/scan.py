"""Scan an existing codebase for smells and score the result against ground-truth labels.

Pipeline per codebase (no code generation):
  static facts over all files -> static rules (cycles, long method, long params)
  + gates -> SLM judges (prompts built from the skill files) -> findings.

"rules"     predicts a smell whenever its gate fires (or a static rule reports it).
"rules+slm" keeps a gated candidate only if the SLM confirms it at a reported severity
            (medium/high: what the in-loop monitor would feed back to the generator).
Static-rule smells are not judged, so both columns agree on them.
"""
from __future__ import annotations

import csv
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from smells.core.design_parser import parse_class_diagram
from smells.core.judges.gates import design_signatures, gate, static_findings
from smells.core.judges.judges import MULTI_TARGET, SmellJudges, _source_at, _source_of
from smells.core.models import ChatModel, get_model
from smells.core.static_facts import project_facts

EXCLUDE_PARTS = {"unit_tests", "tests", "__pycache__", ".venv", "venv", "build", "dist"}


@dataclass
class Prediction:
    smell: str
    file: str
    target: str  # qualname, or "file::fn@line|file::fn@line" for pairs/clumps
    source: str  # "gate" or "rule"
    reason: str = ""
    slm: dict = field(default_factory=dict)  # verdict details for gated candidates

    def confirmed(self, severities: set[str]) -> bool:
        if self.source == "rule":
            return True
        return any(f["severity"] in severities for f in self.slm.get("findings", []))


def collect_files(root: Path) -> dict[str, str]:
    files = {}
    for p in sorted(Path(root).rglob("*.py")):
        rel = p.relative_to(root)
        if EXCLUDE_PARTS & set(rel.parts) or rel.name.startswith("test_") or rel.name == "conftest.py":
            continue
        files[rel.as_posix()] = p.read_text()
    return files


def _pair_key(target: str) -> frozenset:
    """'a.py::f@3|b.py::g@9' or 'a.py::f|b.py::g' -> {('a.py','f'), ('b.py','g')}"""
    out = set()
    for part in target.split("|"):
        f, _, name = part.strip().partition("::")
        out.add((f, name.rsplit("@", 1)[0]))
    return frozenset(out)


def _matches(pred: Prediction, label: dict) -> bool:
    if pred.smell != label["smell"]:
        return False
    if pred.smell in MULTI_TARGET:
        return _pair_key(pred.target) == _pair_key(label["target"])
    return pred.file == label["file"] and pred.target == label["target"]


def predict(cfg: dict, files: dict[str, str], diagram=None) -> tuple[list[Prediction], float]:
    t0 = time.perf_counter()
    g = cfg["gates"]
    il = cfg["in_loop"]
    pf = project_facts(files, g)
    design = design_signatures(diagram)
    preds: dict[tuple, Prediction] = {}
    for path in files:
        for h in gate(pf, path, g):
            if h.judge not in il["judges"]:
                continue
            key = (h.judge, _pair_key(h.target) if h.judge in MULTI_TARGET else (path, h.target))
            preds.setdefault(key, Prediction(h.judge, path, h.target, "gate", h.reason, {"hit": h}))
        for f in static_findings(pf, path, g, design):
            if f.smell not in il.get("static_only_smells", []) and f.smell != "syntax_error":
                continue
            if f.severity not in il["report_severities"]:
                continue
            preds.setdefault((f.smell, (path, f.location)), Prediction(f.smell, path, f.location, "rule", f.evidence))
    return list(preds.values()), time.perf_counter() - t0


def _score(preds: list[Prediction], labels: dict, smells: list[str], confirmed) -> dict:
    pos, neg = labels.get("smells", []), labels.get("negatives", [])
    border = labels.get("borderline", [])
    out = {}
    for s in smells:
        P = [l for l in pos if l["smell"] == s]
        N = [l for l in neg if l["smell"] == s]
        mine = [p for p in preds if p.smell == s and confirmed(p)]
        tp = sum(any(_matches(p, l) for p in mine) for l in P)
        fp_labelled = sum(any(_matches(p, l) for p in mine) for l in N)
        unlabelled = [p for p in mine if not any(_matches(p, l) for l in [*P, *N, *border])]
        fp = fp_labelled + len(unlabelled)
        fn = len(P) - tp
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / len(P) if P else None
        out[s] = {"positives": len(P), "negatives": len(N), "tp": tp, "fp": fp, "fn": fn,
                  "unlabelled_fp": [p.target for p in unlabelled], "precision": prec, "recall": rec}
    return out


def _excerpt(p: Prediction, files: dict[str, str], max_lines: int = 40) -> str:
    if p.smell in MULTI_TARGET:
        parts = []
        for part in p.target.split("|"):
            f, ref = part.split("::", 1)
            name, line = ref.rsplit("@", 1)
            parts.append(f"# {f}\n" + _source_at(files.get(f, ""), name, int(line)))
        code = "\n\n".join(parts)
    else:
        code = _source_of(files.get(p.file, ""), p.target)
    lines = code.splitlines()
    return "\n".join(lines[:max_lines] + (["# ..."] if len(lines) > max_lines else []))


def write_review_csv(res: dict, files: dict[str, str], preds: list[Prediction], path: Path) -> None:
    """One row per candidate: code, SLM verdict and evidence, plus empty columns for a human."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "smell", "file", "target", "source", "gate_reason", "slm_confirmed", "slm_severity",
                    "slm_evidence", "slm_fix", "code", "human_label (smell/not/unsure)", "human_notes"])
        for i, (p, row) in enumerate(zip(preds, res["predictions"]), 1):
            f = (p.slm.get("findings") or [{}])[0]
            w.writerow([i, p.smell, p.file, p.target, p.source, p.reason, row.get("confirmed"),
                        f.get("severity", ""), f.get("evidence", ""), f.get("fix", ""), _excerpt(p, files), "", ""])


def scan(cfg: dict, root: Path, labels_path: Path | None = None, use_slm: bool = True,
         slm: ChatModel | None = None, out: Path | None = None, include: list[str] | None = None,
         max_per_smell: int | None = None, seed: int = 0, review_csv: Path | None = None) -> dict:
    root = Path(root)
    files = collect_files(root)
    if include:
        files = {k: v for k, v in files.items() if any(k.startswith(i.rstrip("/") + "/") or k == i for i in include)}
    uml = root / "docs" / "UML_class.md"
    diagram = parse_class_diagram(uml.read_text()) if uml.exists() else None
    preds, static_s = predict(cfg, files, diagram)
    candidates_total = len(preds)
    if max_per_smell:
        rng = random.Random(seed)
        kept = []
        for smell in sorted({p.smell for p in preds}):
            group = [p for p in preds if p.smell == smell]
            kept += group if len(group) <= max_per_smell else rng.sample(group, max_per_smell)
        preds = kept
    il = cfg["in_loop"]
    severities = set(il["report_severities"])
    slm_stats = {"calls": 0, "latency_s": 0.0, "tokens_in": 0, "tokens_out": 0, "invalid_dropped": 0, "retries": 0}
    if use_slm:
        slm = slm or get_model(cfg, "judge_code")
        judges = SmellJudges(slm, diagram, enabled=il["judges"],
                             json_mode=cfg["models"]["judge_code"].get("json_mode", False), options=cfg.get("judge"))
        for p in preds:
            if p.source != "gate":
                continue
            jr = judges.judge(p.slm.pop("hit"), files)
            p.slm.update(findings=[f.to_dict() for f in jr.findings], latency_s=round(jr.latency_s, 2),
                         invalid=jr.invalid_dropped, retries=jr.retries, rejected_by=jr.rejected_by)
            for k, v in (("calls", jr.calls), ("latency_s", jr.latency_s), ("tokens_in", jr.tokens_in),
                         ("tokens_out", jr.tokens_out), ("invalid_dropped", jr.invalid_dropped),
                         ("retries", jr.retries)):
                slm_stats[k] += v
    for p in preds:
        p.slm.pop("hit", None)
    res = {
        "codebase": str(root), "files": len(files), "loc": sum(len(c.splitlines()) for c in files.values()),
        "candidates": len(preds), "candidates_before_sampling": candidates_total, "static_s": round(static_s, 3),
        "slm_model": getattr(slm, "name", None) if use_slm else None,
        "slm_temperature": cfg["models"]["judge_code"].get("temperature") if use_slm else None,
        "slm": {**slm_stats, "latency_s": round(slm_stats["latency_s"], 2),
                "mean_latency_s": round(slm_stats["latency_s"] / slm_stats["calls"], 2) if slm_stats["calls"] else None},
        "predictions": [{"smell": p.smell, "file": p.file, "target": p.target, "source": p.source,
                         "reason": p.reason, "confirmed": p.confirmed(severities) if use_slm or p.source == "rule" else None,
                         **({"slm": p.slm} if p.slm else {})} for p in preds],
    }
    if labels_path:
        labels = yaml.safe_load(Path(labels_path).read_text())
        enabled = set(il["judges"]) | set(il.get("static_only_smells", []))
        smells = sorted({l["smell"] for l in labels.get("smells", []) + labels.get("negatives", [])} & enabled)
        res["scores"] = {"rules": _score(preds, labels, smells, lambda p: True)}
        if use_slm:
            res["scores"]["rules+slm"] = _score(preds, labels, smells, lambda p: p.confirmed(severities))
        res["verdicts"] = []
        for section in ("smells", "negatives", "borderline"):
            for l in labels.get(section, []):
                if l["smell"] not in enabled:
                    continue
                hit = [p for p in preds if _matches(p, l)]
                res["verdicts"].append({
                    "id": l["id"], "kind": section, "smell": l["smell"], "target": l["target"],
                    "rules": bool(hit),
                    "slm": (any(p.confirmed(severities) for p in hit) if use_slm else None),
                    "slm_evidence": next((f["evidence"] for p in hit for f in p.slm.get("findings", [])), None),
                })
    res["by_smell"] = {}
    for smell in sorted({p.smell for p in preds}):
        group = [p for p in preds if p.smell == smell]
        judged = [p for p in group if p.source == "gate" and use_slm]
        res["by_smell"][smell] = {
            "candidates": len(group), "decided_by": "rule" if group[0].source == "rule" else "slm",
            "judged": len(judged), "confirmed": sum(p.confirmed(severities) for p in judged) if judged else None,
            "mean_latency_s": round(sum(p.slm.get("latency_s", 0) for p in judged) / len(judged), 1) if judged else None,
        }
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(res, indent=2, default=str))
    if review_csv:
        write_review_csv(res, files, preds, review_csv)
    return res


def format_report(res: dict) -> str:
    sampled = (f" (sampled from {res['candidates_before_sampling']})"
               if res.get("candidates_before_sampling", res["candidates"]) != res["candidates"] else "")
    lines = [f"Scanned {res['codebase']}: {res['files']} files, {res['loc']} lines, "
             f"{res['candidates']} candidates{sampled} (static analysis {res['static_s']}s)"]
    if res["slm_model"]:
        s = res["slm"]
        lines.append(f"SLM {res['slm_model']}: {s['calls']} calls, {s['latency_s']}s total "
                     f"({s['mean_latency_s']}s/call), invalid JSON dropped {s['invalid_dropped']}, retries {s['retries']}")
    if "scores" not in res and res.get("by_smell"):
        lines += ["", "| smell | candidates | decided by | judged | SLM confirmed | confirm rate | s/call |",
                  "|---|---|---|---|---|---|---|"]
        for smell, b in res["by_smell"].items():
            rate = f"{b['confirmed'] / b['judged']:.0%}" if b["judged"] else "-"
            lines.append(f"| {smell} | {b['candidates']} | {b['decided_by']} | {b['judged'] or '-'} | "
                         f"{'-' if b['confirmed'] is None else b['confirmed']} | {rate} | {b['mean_latency_s'] or '-'} |")
    if "scores" in res:
        cols = list(res["scores"])
        lines += ["", "| smell | pos | neg | " + " | ".join(f"{c} P | {c} R" for c in cols) + " |",
                  "|---|---|---|" + "---|---|" * len(cols)]
        fmt = lambda x: "-" if x is None else f"{x:.2f}"
        for smell, r in res["scores"]["rules"].items():
            row = [smell, str(r["positives"]), str(r["negatives"])]
            for c in cols:
                rc = res["scores"][c][smell]
                row += [fmt(rc["precision"]), fmt(rc["recall"])]
            lines.append("| " + " | ".join(row) + " |")
        lines += ["", "| id | kind | smell | target | rules | slm | slm evidence |", "|---|---|---|---|---|---|---|"]
        for v in res["verdicts"]:
            mark = lambda b: "-" if b is None else ("yes" if b else "no")
            ev = (v["slm_evidence"] or "")[:70].replace("|", "/")
            lines.append(f"| {v['id']} | {v['kind']} | {v['smell']} | {v['target'][-48:]} | "
                         f"{mark(v['rules'])} | {mark(v['slm'])} | {ev} |")
    return "\n".join(lines)
