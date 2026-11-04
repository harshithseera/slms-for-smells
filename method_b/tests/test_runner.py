"""End-to-end runner tests with fake LLM/SLM on a tiny synthetic DevBench-style project."""
import json

import pytest

from smells.generation import baseline
from smells.generation import in_loop
from smells.core.design_parser import load_project
from smells.core.models import ChatResult, FakeChatModel, ToolCall
from smells.core.runlog import read_events
from smells.config import load_config

DUP = '''
def total_price(items):
    s = 0
    for it in items:
        if it.qty > 0:
            s += it.qty * it.price
    return round(s, 2)

def order_sum(lines):
    acc = 0
    for ln in lines:
        if ln.qty > 0:
            acc += ln.qty * ln.price
    return round(acc, 2)
'''
CLEAN = '''
def total_price(items):
    s = 0
    for it in items:
        if it.qty > 0:
            s += it.qty * it.price
    return round(s, 2)

def order_sum(lines):
    return total_price(lines)
'''


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "devbench" / "shop"
    (root / "shop").mkdir(parents=True)
    (root / "unit_tests").mkdir()
    (root / "shop" / "__init__.py").write_text("")
    (root / "shop" / "prices.py").write_text("# reference implementation, must not leak\n")
    (root / "unit_tests" / "test_prices.py").write_text("SECRET_TEST = 1\n")
    (root / "PRD.md").write_text("# PRD\nCompute prices.")
    (root / "UML_class.md").write_text("```mermaid\nclassDiagram\n  class Item {\n    +qty Int\n  }\n```")
    (root / "UML_sequence.md").write_text("```mermaid\nsequenceDiagram\n  participant U\n```")
    (root / "architecture_design.md").write_text("shop/prices.py")
    (root / "repo_config.json").write_text(json.dumps({"code_file_DAG": {"shop/prices.py": []}}))
    return load_project(tmp_path / "devbench", "shop")


def writer(codes):
    """Fake codegen: each call writes the next code via the write_file tool."""
    it = iter(codes)

    def respond(messages, tools, json_mode):
        nxt = next(it, None)
        if nxt is None:
            return ChatResult(text="done")
        return ChatResult(text="", tool_calls=[ToolCall("c1", "write_file", {"path": "shop/prices.py", "content": nxt})],
                          tokens_in=100, tokens_out=50)

    return FakeChatModel(respond, name="fake-llm")


DUP_FINDING = ('{"findings": [{"smell": "duplicated_logic", "location": "shop/prices.py::total_price | '
               'shop/prices.py::order_sum", "severity": "high", "evidence": "same loop", "fix": "reuse total_price"}]}')


# The loop mechanics are smell-agnostic; these tests drive them with duplicated logic.
MECH = {"in_loop": {"judges": ["duplicated_logic"], "static_only_smells": ["long_parameter_list"]}}


def test_in_loop_feeds_findings_back_and_stops_when_clean(project, tmp_path):
    cfg = load_config(overrides=MECH)
    llm = writer([DUP, CLEAN])
    slm = FakeChatModel(lambda *a: DUP_FINDING, name="fake-slm")
    code_dir = in_loop.run(project, cfg, tmp_path / "runs", llm=llm, slm=slm, run_tests=False)
    assert (code_dir / "shop" / "prices.py").read_text() == CLEAN
    # second LLM call received the finding as a tool result
    tool_msgs = [m for m in llm.calls[1] if m["role"] == "tool"]
    assert "duplicated_logic" in tool_msgs[-1]["content"]
    # nothing from the tests or the reference implementation reached any model
    for call in llm.calls + slm.calls:
        blob = json.dumps(call)
        assert "SECRET_TEST" not in blob and "must not leak" not in blob
    summary = json.loads((code_dir.parent / "summary.json").read_text())
    assert summary["in_loop"]["fix_rounds"] == 1 and summary["in_loop"]["units_clean"] == 1
    assert summary["slm_calls"] == 1  # second version has no duplicate -> no gate -> no SLM call
    events = read_events(code_dir.parent / "events.jsonl")
    checks = [e for e in events if e["event"] == "monitor_check" and e["phase"] == "unit"]
    assert [c["attempt"] for c in checks] == [0, 1]
    assert {"run_start", "llm_call", "unit_done", "final_pass", "run_end"} <= {e["event"] for e in events}


def test_in_loop_respects_fix_budget(project, tmp_path):
    cfg = load_config(overrides=MECH)
    llm = writer([DUP, DUP, DUP, DUP, DUP])
    slm = FakeChatModel(lambda *a: DUP_FINDING)
    in_loop.run(project, cfg, tmp_path / "runs", llm=llm, slm=slm, run_tests=False)
    # 1 initial write + max_fix_rounds revisions
    assert len(llm.calls) == 1 + cfg["in_loop"]["max_fix_rounds"]


def test_in_loop_counts_oscillation(project, tmp_path):
    cfg = load_config(overrides=MECH)
    long_fn = "def f(a, b, c, d, e, g, h):\n    return 1\n"
    llm = writer([DUP, long_fn, CLEAN])
    slm = FakeChatModel(lambda *a: DUP_FINDING)
    code_dir = in_loop.run(project, cfg, tmp_path / "runs", llm=llm, slm=slm, run_tests=False)
    s = json.loads((code_dir.parent / "summary.json").read_text())
    assert s["in_loop"]["oscillations"] == 1  # the fix introduced long_parameter_list
    assert s["in_loop"]["resolved"] >= 2


def test_baseline_single_pass_no_slm(project, tmp_path):
    cfg = load_config()
    llm = writer([DUP, CLEAN])
    code_dir = baseline.run(project, cfg, tmp_path / "runs", llm=llm, run_tests=False)
    assert (code_dir / "shop" / "prices.py").read_text() == DUP
    assert len(llm.calls) == 1
    s = json.loads((code_dir.parent / "summary.json").read_text())
    assert s["quality"]["duplicate_pairs"] == 1 and s["slm_calls"] == 0


def test_static_only_ablation_never_calls_slm(project, tmp_path):
    cfg = load_config()
    code_dir = in_loop.run(project, cfg, tmp_path / "runs", llm=writer([DUP]), run_tests=False, use_slm=False)
    s = json.loads((code_dir.parent / "summary.json").read_text())
    assert s["mode"] == "in_loop_static" and s["slm_calls"] == 0


def test_fenced_code_fallback(project, tmp_path):
    cfg = load_config(overrides={"models": {"codegen": {"use_tools": False}}})
    llm = FakeChatModel(lambda *a: ChatResult(text=f"```python\n{CLEAN}```"))
    code_dir = baseline.run(project, cfg, tmp_path / "runs", llm=llm, run_tests=False)
    assert (code_dir / "shop" / "prices.py").read_text().strip() == CLEAN.strip()


def test_default_scope_is_code_smells_only():
    from smells.core.schema import CODE_SMELLS
    il = load_config()["in_loop"]
    assert set(il["judges"]) | set(il["static_only_smells"]) == set(CODE_SMELLS)


def test_disabled_smell_is_neither_judged_nor_fed_back(project, tmp_path):
    cfg = load_config(overrides={"in_loop": {"judges": ["magic_numbers"]}})
    llm = writer([DUP, CLEAN])
    slm = FakeChatModel(lambda *a: DUP_FINDING)
    code_dir = in_loop.run(project, cfg, tmp_path / "runs", llm=llm, slm=slm, run_tests=False)
    assert slm.calls == [] and len(llm.calls) == 1
    assert (code_dir / "shop" / "prices.py").read_text() == DUP
