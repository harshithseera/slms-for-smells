"""SLM smell judges: one smell per call, prompts built from the skill files, strict JSON.

Each call sees the shared rules of ONE skill file plus the ONE smell section being
judged (see smells.core.skills), followed by the candidate's code and static facts.

Output schema (validated):
  {"findings": [{"smell", "location", "severity": low|medium|high, "evidence", "fix"}]}
Invalid output gets one retry with the validation error, and is then dropped and counted.
"""
from __future__ import annotations

import ast
import json
import re
import time
from dataclasses import dataclass, field

from smells.core.design_parser import ClassDiagram
from smells.core.judges.gates import GateHit
from smells.core.models import ChatModel
from smells.core.schema import SEVERITIES, Finding
from smells.core.skills import skill_for

SLM_JUDGES = ("duplicated_logic", "magic_numbers", "primitive_obsession", "data_clumps", "message_chains",
              "flag_argument")
MULTI_TARGET = ("duplicated_logic", "data_clumps")  # candidates that span 2+ functions

TASK = """---

## Your task

Check for exactly one smell: **{smell}**. Candidate: {what}.

{reason}

Static facts (deterministic, trust them):
{facts}
{design}
{code}

{answer}"""

ANSWER_PLAIN = """Reply with JSON only. Use `"smell": "{smell}"` and `"location": "{location}"`.
If the smell is not present, reply {{"findings": []}}."""

ANSWER_CHECKLIST = """First check each reject rule against the code above:
{rules}

Reply with JSON only, in this shape:
{{"reject": {{{keys}}}, "findings": [...]}}
Set a rule to true if it applies to this code. If ANY rule is true, "findings" must be [].
Otherwise give the finding with `"smell": "{smell}"` and `"location": "{location}"`, or []
if the smell is not present."""
REASON_SHOWN = "Why the analyser flagged it: {reason}"
REASON_NEUTRAL = "A static analyser selected this candidate for review. That is not evidence of the smell."


class InvalidJudgeOutput(ValueError):
    pass


def _load_json(text: str):
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    if not t.startswith(("{", "[")):
        m = re.search(r"[{\[].*[}\]]", t, re.DOTALL)
        if not m:
            raise InvalidJudgeOutput("no JSON object found")
        t = m.group(0)
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        raise InvalidJudgeOutput(f"invalid JSON: {e}") from e


def parse_reject(text: str) -> list[str]:
    """Reject-rule ids the judge marked as applying (true), from {"reject": {"R1": true, ...}}."""
    data = _load_json(text)
    rej = data.get("reject") if isinstance(data, dict) else None
    if not isinstance(rej, dict):
        return []
    return sorted(k for k, v in rej.items() if v is True or str(v).strip().lower() in ("true", "yes"))


def parse_judge_json(text: str, smell: str) -> list[dict]:
    """Parse and validate judge output. Raises InvalidJudgeOutput with a reason."""
    data = _load_json(text)
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "findings" in data:
        items = data["findings"]
    elif isinstance(data, dict) and "smell" in data:
        items = [data]
    else:
        raise InvalidJudgeOutput('expected {"findings": [...]}')
    if not isinstance(items, list):
        raise InvalidJudgeOutput("findings must be a list")
    out = []
    for it in items:
        if not isinstance(it, dict):
            raise InvalidJudgeOutput("each finding must be an object")
        missing = [k for k in ("smell", "location", "severity", "evidence", "fix") if not it.get(k)]
        if missing:
            raise InvalidJudgeOutput(f"finding missing fields: {missing}")
        sev = str(it["severity"]).lower().strip()
        if sev not in SEVERITIES:
            raise InvalidJudgeOutput(f"severity must be one of {SEVERITIES}, got {sev!r}")
        if str(it["smell"]).strip().lower().replace(" ", "_") != smell:
            continue  # off-topic finding from a one-smell judge: ignore
        out.append({**{k: str(it[k]).strip() for k in ("location", "evidence", "fix")}, "severity": sev})
    return out


def _source_of(code: str, qualname: str) -> str:
    """Source of a class/function by qualname ("Cls", "Cls.meth", "func")."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    parts = qualname.split(".")
    nodes = tree.body
    found = None
    for p in parts:
        found = next(
            (n for n in nodes if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == p),
            None,
        )
        if found is None:
            return code
        nodes = getattr(found, "body", [])
    return ast.get_source_segment(code, found) or code


def _source_at(code: str, name: str, lineno: int) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name and n.lineno == lineno:
            return ast.get_source_segment(code, n) or ""
    return ""


def _design_excerpt(diagram: ClassDiagram | None, names: list[str], limit: int = 2500) -> str:
    if diagram is None or not diagram.classes:
        return "(no class diagram)"
    picked = [c for n, c in diagram.classes.items() if n in names] or list(diagram.classes.values())
    lines = []
    for c in picked:
        lines.append(f"class {c.name}" + (f" <<{c.stereotype}>>" if c.stereotype else ""))
        lines += [f"  {a}" for a in c.attributes] + [f"  {m}" for m in c.methods]
        deps = diagram.dependencies(c.name)
        if deps:
            lines.append(f"  depends on: {', '.join(deps)}")
    return "\n".join(lines)[:limit]


@dataclass
class JudgeResult:
    findings: list[Finding] = field(default_factory=list)
    invalid_dropped: int = 0
    retries: int = 0
    latency_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    rejected_by: list[str] = field(default_factory=list)  # reject-rule ids the judge said apply


class SmellJudges:
    def __init__(self, model: ChatModel, diagram: ClassDiagram | None = None, enabled=SLM_JUDGES, json_mode=True,
                 options: dict | None = None):
        self.model = model
        self.diagram = diagram
        self.enabled = set(enabled)
        self.json_mode = json_mode
        opts = options or {}
        self.show_gate_reason = opts.get("show_gate_reason", False)
        self.show_gate_reason_for = set(opts.get("show_gate_reason_for", []))
        self.reject_checklist = opts.get("reject_checklist", True)

    def _reason(self, hit: GateHit) -> str:
        show = self.show_gate_reason or hit.judge in self.show_gate_reason_for
        return REASON_SHOWN.format(reason=hit.reason) if show else REASON_NEUTRAL

    def _answer(self, skill, smell: str, location: str) -> str:
        rules = skill.reject_rules() if self.reject_checklist else []
        if not rules:
            return ANSWER_PLAIN.format(smell=smell, location=location)
        return ANSWER_CHECKLIST.format(
            rules="\n".join(f"R{i}: {r}" for i, r in enumerate(rules, 1)),
            keys=", ".join(f'"R{i}": true|false' for i in range(1, len(rules) + 1)),
            smell=smell, location=location)

    def build_prompt(self, hit: GateHit, files: dict[str, str]) -> str:
        skill = skill_for(hit.judge)
        facts = json.dumps(hit.facts, default=str)[:1500]
        if hit.judge in MULTI_TARGET:
            locs, blocks = [], []
            for i, part in enumerate(hit.target.split("|")):
                f, ref = part.split("::", 1)
                name, line = ref.rsplit("@", 1)
                locs.append(f"{f}::{name}")
                blocks.append(f"Function {'ABC'[i]} (`{f}::{name}`):\n```python\n"
                              f"{_source_at(files.get(f, ''), name, int(line))}\n```")
            task = TASK.format(smell=hit.judge, what=" and ".join(f"`{l}`" for l in locs), reason=self._reason(hit),
                               facts=facts, design="", code="\n\n".join(blocks),
                               answer=self._answer(skill, hit.judge, " | ".join(locs)))
        else:
            src = _source_of(files[hit.file], hit.target)[:8000]
            names = [hit.target.split(".")[0], *hit.facts.get("referenced", [])]
            design = f"\nDesign excerpt (UML class diagram):\n{_design_excerpt(self.diagram, names)}\n"
            task = TASK.format(smell=hit.judge, what=f"`{hit.target}` in `{hit.file}`", reason=self._reason(hit),
                               facts=facts, design=design,
                               code=f"Code of `{hit.target}`:\n```python\n{src}\n```",
                               answer=self._answer(skill, hit.judge, hit.target))
        return f"{skill.prompt_text()}\n\n{task}"

    def judge(self, hit: GateHit, files: dict[str, str]) -> JudgeResult:
        res = JudgeResult()
        if hit.judge not in self.enabled:
            return res
        messages = [{"role": "user", "content": self.build_prompt(hit, files)}]
        for attempt in range(2):
            t0 = time.perf_counter()
            out = self.model.chat(messages, json_mode=self.json_mode)
            res.latency_s += time.perf_counter() - t0
            res.tokens_in += out.tokens_in
            res.tokens_out += out.tokens_out
            res.calls += 1
            try:
                items = parse_judge_json(out.text, hit.judge)
            except InvalidJudgeOutput as e:
                if attempt == 0:
                    res.retries += 1
                    messages += [
                        {"role": "assistant", "content": out.text},
                        {"role": "user", "content": f"Your output was rejected ({e}). Reply with the JSON object only."},
                    ]
                    continue
                res.invalid_dropped += 1
                return res
            if self.reject_checklist:
                res.rejected_by = parse_reject(out.text)
                if res.rejected_by:
                    items = []  # a reject rule applies: no finding, whatever the model wrote
            res.findings = [
                Finding(hit.judge, it["location"], it["severity"], it["evidence"], it["fix"],
                        source=f"slm:{self.model.name}", file=hit.file)
                for it in items
            ]
            return res
        return res
