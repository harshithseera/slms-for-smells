import pytest

from smells.core.judges.gates import GateHit
from smells.core.judges.judges import InvalidJudgeOutput, SmellJudges, parse_judge_json
from smells.core.models import FakeChatModel

GOOD = '{"findings": [{"smell": "magic_numbers", "location": "fee", "severity": "High", "evidence": "e", "fix": "f"}]}'


def test_parse_valid_and_fenced():
    assert parse_judge_json(GOOD, "magic_numbers")[0]["severity"] == "high"
    assert len(parse_judge_json("Sure!\n```json\n" + GOOD + "\n```", "magic_numbers")) == 1
    assert parse_judge_json('{"findings": []}', "magic_numbers") == []


def test_parse_drops_off_topic_findings():
    txt = '{"findings": [{"smell": "long_method", "location": "x", "severity": "low", "evidence": "e", "fix": "f"}]}'
    assert parse_judge_json(txt, "magic_numbers") == []


@pytest.mark.parametrize(
    "bad",
    [
        "not json at all",
        '{"findings": [{"smell": "magic_numbers"}]}',
        '{"findings": [{"smell": "magic_numbers", "location": "a", "severity": "critical", "evidence": "e", "fix": "f"}]}',
        '{"oops": 1}',
    ],
)
def test_parse_invalid(bad):
    with pytest.raises(InvalidJudgeOutput):
        parse_judge_json(bad, "magic_numbers")


CODE = "def fee(x):\n    return x * 0.9\n"
HIT = GateHit("magic_numbers", "m.py", "fee", "numeric literals [0.9]", {"literals": [{"value": 0.9, "line": 2}]})


def test_judge_retries_once_then_succeeds():
    outs = iter(["garbage", GOOD])
    model = FakeChatModel(lambda *a: next(outs))
    res = SmellJudges(model).judge(HIT, {"m.py": CODE})
    assert res.retries == 1 and res.invalid_dropped == 0 and res.calls == 2
    assert res.findings[0].location == "fee" and res.findings[0].source == "slm:fake"
    # the retry message tells the model why it was rejected
    assert "rejected" in model.calls[1][-1]["content"]


def test_judge_drops_after_second_invalid():
    res = SmellJudges(FakeChatModel(lambda *a: "garbage")).judge(HIT, {"m.py": CODE})
    assert res.findings == [] and res.invalid_dropped == 1 and res.calls == 2


def test_prompt_is_built_from_one_skill_section():
    model = FakeChatModel(lambda *a: '{"findings": []}')
    SmellJudges(model).judge(HIT, {"m.py": CODE})
    prompt = model.calls[0][0]["content"]
    assert "def fee" in prompt
    assert "## Rules" in prompt and "## Smell: magic_numbers" in prompt
    # only the judged smell's section, never the rest of the file or the other skill file
    assert prompt.count("## Smell:") == 1 and "duplicated_logic" not in prompt.split("## Your task")[0]
    assert "<!--" not in prompt and '"location": "fee"' in prompt


def test_duplicate_prompt_extracts_both_functions():
    code = "def a(x):\n    return x + 1\n\ndef b(y):\n    return y + 1\n"
    hit = GateHit("duplicated_logic", "m.py", "m.py::a@1|m.py::b@4", "sim 1.0", {})
    model = FakeChatModel(lambda *a: '{"findings": []}')
    SmellJudges(model).judge(hit, {"m.py": code})
    p = model.calls[0][0]["content"]
    assert "def a(x)" in p and "def b(y)" in p
    assert "## Smell: duplicated_logic" in p and p.count("## Smell:") == 1
    assert '"location": "m.py::a | m.py::b"' in p


def test_skill_sections_exist_for_every_slm_judge():
    from smells.core.judges.judges import SLM_JUDGES
    from smells.core.skills import load_skills
    assert set(SLM_JUDGES) <= set(load_skills())


def test_reject_checklist_overrides_findings():
    out = ('{"reject": {"R1": false, "R2": true}, "findings": [{"smell": "magic_numbers", "location": "fee", '
           '"severity": "high", "evidence": "e", "fix": "f"}]}')
    res = SmellJudges(FakeChatModel(lambda *a: out)).judge(HIT, {"m.py": CODE})
    assert res.findings == [] and res.rejected_by == ["R2"]
    keep = out.replace('"R2": true', '"R2": false')
    assert len(SmellJudges(FakeChatModel(lambda *a: keep)).judge(HIT, {"m.py": CODE}).findings) == 1


def test_prompt_lists_reject_rules_and_hides_gate_reason():
    model = FakeChatModel(lambda *a: '{"reject": {}, "findings": []}')
    SmellJudges(model).judge(HIT, {"m.py": CODE})
    p = model.calls[0][0]["content"]
    assert "R1:" in p and '"reject"' in p and "numeric literals [0.9]" not in p
    shown = FakeChatModel(lambda *a: '{"findings": []}')
    SmellJudges(shown, options={"show_gate_reason": True, "reject_checklist": False}).judge(HIT, {"m.py": CODE})
    p2 = shown.calls[0][0]["content"]
    assert "numeric literals [0.9]" in p2 and "R1:" not in p2


def test_gate_reason_can_be_shown_for_one_smell_only():
    dup = GateHit("duplicated_logic", "m.py", "m.py::a@1|m.py::b@4", "AST similarity 0.97", {})
    code = "def a(x):\n    return x + 1\n\ndef b(y):\n    return y + 1\n"
    m = FakeChatModel(lambda *a: '{"reject": {}, "findings": []}')
    j = SmellJudges(m, options={"show_gate_reason_for": ["duplicated_logic"]})
    j.judge(dup, {"m.py": code})
    j.judge(HIT, {"m.py": CODE})
    assert "AST similarity 0.97" in m.calls[0][0]["content"]
    assert "numeric literals [0.9]" not in m.calls[1][0]["content"]
