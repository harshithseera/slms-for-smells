"""Repair pass end to end on gymdesk with fake models (real gymdesk tests)."""
import json
import sys
from pathlib import Path

from smells.core.models import ChatResult, FakeChatModel
from smells.config import load_config
from smells.eval.repair import repair, select_findings
from smells.eval.scan import scan

ROOT = Path(__file__).parents[1] / "data" / "mock_codebase"
CODE, LABELS = ROOT / "gymdesk", ROOT / "labels.yaml"
CONFIRM = ('{"reject": {}, "findings": [{"smell": "%s", "location": "x", "severity": "medium", '
           '"evidence": "e", "fix": "f"}]}')


def _slm(messages, tools, json_mode):
    import re
    return CONFIRM % re.search(r"exactly one smell: \*\*(\w+)\*\*", messages[0]["content"]).group(1)


def _echo_llm(messages, tools, json_mode):
    """Returns the file unchanged, except one public function gets a harmless docstring."""
    import re
    code = re.search(r"Current content of `[^`]+`:\n```python\n(.*?)```", messages[-1]["content"], re.S).group(1)
    return ChatResult(text=f"```python\n# refactored\n{code}```")


def test_select_findings_conditions(tmp_path):
    res = scan(load_config(), CODE, None, slm=FakeChatModel(lambda *a: '{"reject": {"R1": true}, "findings": []}'))
    assert len(select_findings(res, "rules")) == res["candidates"]
    assert all(f["source"] == "rule" for f in select_findings(res, "slm"))  # SLM rejected everything


def test_repair_pass_with_fake_models(tmp_path):
    cfg = load_config()
    before = scan(cfg, CODE, LABELS, slm=FakeChatModel(_slm), out=tmp_path / "before.json")
    res = repair(cfg, CODE, tmp_path / "before.json", "slm", tmp_path / "slm", sys.executable, ["unit_tests"],
                 labels=LABELS, llm=FakeChatModel(_echo_llm), slm=FakeChatModel(_slm), recheck="slm")
    assert res["files_edited"] >= 5 and all(e["status"] == "repaired" for e in res["edits"])
    assert res["tests"]["fixed_set"] == 20 and res["tests"]["pass_rate"] == 1.0
    assert (tmp_path / "slm" / "code" / "gymdesk" / "billing.py").read_text().startswith("# refactored")
    s = res["smells"]["confirmed"]["_total"]
    assert s["introduced"] == 0 and s["resolved"] == 0  # code unchanged -> same findings
    assert json.loads((tmp_path / "slm" / "repair.json").read_text())["condition"] == "slm"
    assert not (CODE / "gymdesk" / "billing.py").read_text().startswith("# refactored")  # original untouched


def test_static_recheck_writes_diffs(tmp_path):
    cfg = load_config()
    scan(cfg, CODE, None, slm=FakeChatModel(_slm), out=tmp_path / "before.json")
    res = repair(cfg, CODE, tmp_path / "before.json", "rules", tmp_path / "r", sys.executable, ["unit_tests"],
                 llm=FakeChatModel(_echo_llm))
    assert res["recheck"] == "static" and "candidates" in res["smells"] and "confirmed" not in res["smells"]
    diffs = list((tmp_path / "r" / "diffs").glob("*.diff"))
    assert diffs and all("+# refactored" in d.read_text() for d in diffs)


def test_import_check_retries_then_reverts(tmp_path):
    cfg = load_config()
    scan(cfg, CODE, None, slm=FakeChatModel(_slm), out=tmp_path / "before.json")
    calls = {"n": 0}

    def broken_llm(messages, tools, json_mode):
        calls["n"] += 1
        return ChatResult(text="```python\nimport gymdesk.nonexistent_module\n```")
    res = repair(cfg, CODE, tmp_path / "before.json", "slm", tmp_path / "b", sys.executable, ["unit_tests"],
                 llm=FakeChatModel(broken_llm), recheck="none")
    assert all(e["status"] == "reverted: does not import" and e["import_retries"] == 1 for e in res["edits"])
    assert res["tests"]["pass_rate"] == 1.0  # every broken file was reverted to the original
