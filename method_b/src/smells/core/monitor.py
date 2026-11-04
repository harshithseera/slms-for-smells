"""The monitor: static facts -> static rule findings + gated SLM judges."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from smells.core.judges.gates import GateHit, design_signatures, gate, static_findings
from smells.core.judges.judges import SmellJudges
from smells.core.schema import Finding
from smells.core.static_facts import ProjectFacts, project_facts


@dataclass
class MonitorReport:
    path: str
    facts: dict
    gate_hits: list[GateHit]
    findings: list[Finding]  # all findings (static + SLM), before severity filter
    reported: list[Finding]  # findings at report_severities: these go back to the LLM
    invalid_dropped: int = 0
    judge_retries: int = 0
    static_s: float = 0.0
    slm_s: float = 0.0
    slm_calls: int = 0
    slm_tokens_in: int = 0
    slm_tokens_out: int = 0
    project: ProjectFacts | None = field(default=None, repr=False)


class Monitor:
    def __init__(self, cfg: dict, judges: SmellJudges | None, use_slm: bool = True, diagram=None):
        self.design = design_signatures(diagram)
        self.gates = cfg["gates"]
        self.report_severities = set(cfg["in_loop"]["report_severities"])
        self.static_only = set(cfg["in_loop"].get("static_only_smells", []))
        self.enabled_judges = set(cfg["in_loop"]["judges"])
        self.judges = judges
        self.use_slm = use_slm and judges is not None

    def check(self, path: str, files: dict[str, str]) -> MonitorReport:
        t0 = time.perf_counter()
        pf = project_facts(files, self.gates)
        findings = [
            f for f in static_findings(pf, path, self.gates, self.design)
            if f.smell in self.static_only or f.smell == "syntax_error"
        ]
        hits = [h for h in gate(pf, path, self.gates) if h.judge in self.enabled_judges]
        static_s = time.perf_counter() - t0
        rep = MonitorReport(path, pf.summary_for(path), hits, findings, [], static_s=static_s, project=pf)
        for h in hits:
            if not self.use_slm:
                continue
            jr = self.judges.judge(h, files)
            rep.findings += jr.findings
            rep.invalid_dropped += jr.invalid_dropped
            rep.judge_retries += jr.retries
            rep.slm_s += jr.latency_s
            rep.slm_calls += jr.calls
            rep.slm_tokens_in += jr.tokens_in
            rep.slm_tokens_out += jr.tokens_out
        rep.reported = [f for f in rep.findings if f.severity in self.report_severities]
        return rep


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return "No smells found."
    lines = []
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. [{f.severity}] {f.smell} at {f.location}: {f.evidence}. Suggested fix: {f.fix}")
    return "\n".join(lines)
