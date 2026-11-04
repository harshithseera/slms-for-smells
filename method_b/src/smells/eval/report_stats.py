"""Collect every report-ready statistic from the result files into one Markdown + JSON summary.

Reads (whatever exists; unfinished runs are skipped):
  results/scan_code_7b*.json      labelled gymdesk scans (precision/recall, ablations, judge temperature)
  results/{httpie,mkdocs}_7b*.json real-code scans (confirm rates, reject-rule use, evidence checks)
  results/repair/*/repair.json     repair runs (+ attribution.json): tests, breakage, churn, cost
"""
from __future__ import annotations

import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

from smells.config import REPO_ROOT

RESULTS = REPO_ROOT / "results"
IDENT = re.compile(r"`([^`]+)`|\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+|[a-z]+_[a-z0-9_]+|[a-z]+[A-Z][A-Za-z0-9]+)\b")


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _pct(x):
    return "-" if x is None else f"{x:.0%}"


def _ms(vals: list[float], fmt="{:.1%}") -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "-"
    if len(vals) == 1:
        return fmt.format(vals[0]) + " (n=1)"
    return f"{fmt.format(st.mean(vals))} ± {fmt.format(st.pstdev(vals))} (n={len(vals)}; {fmt.format(min(vals))}–{fmt.format(max(vals))})"


def _totals(scores: dict) -> tuple:
    tp = sum(v["tp"] for v in scores.values()); fp = sum(v["fp"] for v in scores.values())
    fn = sum(v["fn"] for v in scores.values())
    return tp, fp, fn, (tp / (tp + fp) if tp + fp else None), (tp / (tp + fn) if tp + fn else None)


def _words(t):
    return set(re.findall(r"[a-z_]{3,}", (t or "").lower()))


def scan_stats(path: Path) -> dict | None:
    r = _load(path)
    if not r or "predictions" not in r:
        return None
    judged = [p for p in r["predictions"] if p["source"] == "gate"]
    conf = [p for p in judged if p.get("confirmed")]
    per = defaultdict(Counter)
    sev = Counter()
    echo = 0
    for p in judged:
        c = per[p["smell"]]
        c["judged"] += 1
        c["confirmed"] += bool(p.get("confirmed"))
        c["reject_fired"] += bool(p.get("slm", {}).get("rejected_by"))
        for f in p.get("slm", {}).get("findings", []):
            sev[f.get("severity")] += 1
    for p in conf:
        ev = (p["slm"].get("findings") or [{}])[0].get("evidence", "")
        rw = _words(p["reason"])
        echo += bool(rw) and len(rw & _words(ev)) / len(rw) >= 0.6
    rules = [p for p in r["predictions"] if p["source"] == "rule"]
    out = {
        "file": path.name, "codebase": Path(r["codebase"]).name, "files": r["files"], "loc": r["loc"],
        "candidates": r.get("candidates_before_sampling", r["candidates"]), "judged": len(judged),
        "rule_findings": len(rules), "confirmed": len(conf),
        "confirm_rate": len(conf) / len(judged) if judged else None,
        "reject_rule_rate": sum(c["reject_fired"] for c in per.values()) / len(judged) if judged else None,
        "gate_echo_rate": echo / len(conf) if conf else None,
        "severity": dict(sev), "slm": r.get("slm", {}), "slm_model": r.get("slm_model"),
        "slm_temperature": r.get("slm_temperature") if r.get("slm_temperature") is not None else 0,
        "version": (re.search(r"_(v\d+)", path.name) or re.search(r"(_)", "v1_"))[1] if "_v" in path.name else "v1",
        "per_smell": {s: dict(c) for s, c in sorted(per.items())},
    }
    if "scores" in r:
        for view in r["scores"]:
            tp, fp, fn, p_, rc = _totals(r["scores"][view])
            out[f"{view}_totals"] = {"tp": tp, "fp": fp, "fn": fn, "precision": p_, "recall": rc}
        out["scores"] = r["scores"]
    return out


def repair_stats(run: Path) -> dict | None:
    r = _load(run / "repair.json")
    if not r:
        return None
    a = _load(run / "attribution.json")
    m = re.match(r"(?P<cb>[a-z]+)_(?P<cond>slm|rules)(?:_(?P<tag>.+))?$", run.name)
    if not m:
        return None
    edits = r["edits"]
    status = Counter(e["status"].split(":")[0] for e in edits)
    churn = []  # +/- lines in the saved unified diffs (insertions do not inflate it)
    for dfile in sorted((run / "diffs").glob("*.diff")):
        n = sum(1 for l in dfile.read_text().splitlines()
                if l[:1] in "+-" and not l.startswith(("+++", "---")))
        if n:
            churn.append(n)
    t = r["tests"]
    out = {
        "run": run.name, "codebase": m["cb"], "condition": m["cond"], "tag": m["tag"] or "t0",
        "temperature": r["llm"].get("temperature") if r["llm"].get("temperature") is not None else 0, "findings_sent": r["findings_sent"],
        "files_edited": r["files_edited"], "status": dict(status),
        "format_retries": sum(e.get("format_retries", 0) for e in edits),
        "import_retries": sum(e.get("import_retries", 0) for e in edits),
        "reverted": sum(e["status"].startswith("reverted") for e in edits),
        "public_names_removed": sum(bool(e.get("public_names_removed")) for e in edits),
        "diff_lines_total": sum(churn), "diff_lines_per_file": st.mean(churn) if churn else 0,
        "tests_fixed_set": t["fixed_set"], "tests_still_passing": t["still_passing"], "pass_rate": t["pass_rate"],
        "llm_tokens_in": r["llm"]["tokens_in"], "llm_tokens_out": r["llm"]["tokens_out"], "repair_s": r["repair_s"],
    }
    s = r.get("smells", {})
    if s:
        view = s.get("candidates") or s.get("confirmed") or {}
        tot = view.get("_total", {})
        out.update(recheck_gone=s.get("sent_resolved"), recheck_sent=s.get("sent_total"),
                   recheck_new=tot.get("introduced"))
    if a:
        out.update(files_safe_alone=a["files_safe"], files_checked_alone=len(a["files"]),
                   files_breaking_alone=a["files_breaking"])
    return out


def collect() -> dict:
    scans = [s for p in sorted(RESULTS.glob("*_7b*.json")) if (s := scan_stats(p))]
    repairs = [s for p in sorted((RESULTS / "repair").glob("*")) if p.is_dir() and not p.name.endswith("_v1")
               and (s := repair_stats(p))]
    return {"scans": scans, "repairs": repairs}


def to_markdown(d: dict) -> str:
    L = ["# Method B: report statistics", "", "Generated by `smells stats` from `method_b/results/`.", ""]
    lab = [s for s in d["scans"] if "rules+slm_totals" in s]
    real = [s for s in d["scans"] if "rules+slm_totals" not in s]
    if lab:
        L += ["## 1. Labelled mock codebase (gymdesk): detection", "",
              "| scan file | judge T | precision | recall | TP | FP | FN | s/call | invalid JSON |",
              "|---|---|---|---|---|---|---|---|---|"]
        for s in lab:
            t = s["rules+slm_totals"]
            L.append(f"| {s['file']} | {s['slm_temperature']} | {_pct(t['precision'])} | {_pct(t['recall'])} | "
                     f"{t['tp']} | {t['fp']} | {t['fn']} | {s['slm'].get('mean_latency_s')} | {s['slm'].get('invalid_dropped')} |")
        r0 = lab[0].get("rules_totals")
        if r0:
            L += ["", f"Rules alone (no SLM): precision {_pct(r0['precision'])}, recall {_pct(r0['recall'])}."]
        L.append("")
    if real or lab:
        L += ["## 2. Judge behaviour per scan", "",
              "| scan | lines | candidates | judged | confirmed | confirm rate | reject rule fired | gate echo | "
              "s/call | prompt tok/call | invalid |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in real + lab:
            sl = s["slm"]
            L.append(f"| {s['file']} | {s['loc']} | {s['candidates']} | {s['judged']} | {s['confirmed']} | "
                     f"{_pct(s['confirm_rate'])} | {_pct(s['reject_rule_rate'])} | {_pct(s['gate_echo_rate'])} | "
                     f"{sl.get('mean_latency_s')} | {sl.get('tokens_in', 0) // max(sl.get('calls', 1), 1)} | {sl.get('invalid_dropped')} |")
        pooled = defaultdict(Counter)
        latest = max((s["version"] for s in real), default="v1")
        for s in real:
            if s["version"] != latest:
                continue
            for smell, c in s["per_smell"].items():
                pooled[smell].update(c)
        if pooled:
            L += ["", f"Real code, latest pipeline ({latest}), pooled over codebases, per smell:", "",
                  "| smell | judged | confirmed | confirm rate | reject rule fired |", "|---|---|---|---|---|"]
            for smell, c in sorted(pooled.items()):
                L.append(f"| {smell} | {c['judged']} | {c['confirmed']} | {_pct(c['confirmed'] / c['judged'])} | "
                         f"{_pct(c['reject_fired'] / c['judged'])} |")
        sev = Counter()
        for s in d["scans"]:
            sev.update(s["severity"])
        calls = sum(s["slm"].get("calls", 0) for s in d["scans"])
        secs = sum(s["slm"].get("latency_s", 0) for s in d["scans"])
        L += ["", f"Severity of all returned findings: {dict(sev)}.",
              f"Total SLM calls over all scans: {calls}, total SLM time {secs / 60:.0f} min, "
              f"invalid JSON {sum(s['slm'].get('invalid_dropped', 0) for s in d['scans'])}.", ""]
    if d["repairs"]:
        L += ["## 3. Repair (one LLM pass), per run", "",
              "| run | T | findings sent | files edited | tests passing | files safe alone | diff lines/file | "
              "import retries | reverted | re-check: no longer flagged | newly flagged | LLM tokens in/out |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in d["repairs"]:
            L.append(f"| {r['run']} | {r['temperature']} | {r['findings_sent']} | {r['files_edited']} | "
                     f"{r['tests_still_passing']}/{r['tests_fixed_set']} ({_pct(r['pass_rate'])}) | "
                     f"{r.get('files_safe_alone', '-')}/{r.get('files_checked_alone', '-')} | "
                     f"{r['diff_lines_per_file']:.0f} | {r['import_retries']} | {r['reverted']} | "
                     f"{r.get('recheck_gone', '-')}/{r.get('recheck_sent', '-')} | {r.get('recheck_new', '-')} | "
                     f"{r['llm_tokens_in']}/{r['llm_tokens_out']} |")
        agg = defaultdict(list)
        for r in d["repairs"]:
            agg[(r["codebase"], r["condition"])].append(r)
        L += ["", "## 4. Repair, aggregated over runs (all temperatures and repeats)", "",
              "| codebase | condition | runs | tests still passing | files safe alone | findings sent | diff lines/file |",
              "|---|---|---|---|---|---|---|"]
        for (cb, cond), rs in sorted(agg.items()):
            safe = [r["files_safe_alone"] / r["files_checked_alone"] for r in rs if r.get("files_checked_alone")]
            L.append(f"| {cb} | {cond} | {len(rs)} | {_ms([r['pass_rate'] for r in rs])} | {_ms(safe, '{:.0%}')} | "
                     f"{rs[0]['findings_sent']} | {_ms([r['diff_lines_per_file'] for r in rs], '{:.0f}')} |")
        L.append("")
    return "\n".join(L)


def write(out_md: Path | None = None) -> dict:
    d = collect()
    out_md = out_md or RESULTS / "report_stats.md"
    out_md.write_text(to_markdown(d))
    out_md.with_suffix(".json").write_text(json.dumps(d, indent=2, default=str))
    return d
