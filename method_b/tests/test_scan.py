"""Scanner and the mock codebase's ground truth."""
from pathlib import Path

import yaml

from smells.core.models import FakeChatModel
from smells.config import load_config
from smells.eval.scan import collect_files, predict, scan

ROOT = Path(__file__).parents[1] / "data" / "mock_codebase"
CODE, LABELS = ROOT / "gymdesk", ROOT / "labels.yaml"
YES = ('{"findings": [{"smell": "%s", "location": "x", "severity": "high", '
       '"evidence": "e", "fix": "f"}]}')


def _confirm_all(messages, tools, json_mode):
    import re
    smell = re.search(r"Check for exactly one smell: \*\*(\w+)\*\*", messages[0]["content"]).group(1)
    return YES % smell


def test_scanner_skips_tests_and_reads_package():
    files = collect_files(CODE)
    assert files and all(f.startswith("gymdesk/") for f in files)
    assert not any("test" in Path(f).name for f in files)


def test_every_candidate_is_labelled():
    """Every gate hit / reported static finding has a verdict in labels.yaml."""
    from smells.eval.scan import _matches
    labels = yaml.safe_load(LABELS.read_text())
    every = labels["smells"] + labels["negatives"] + labels["borderline"]
    preds, _ = predict(load_config(), collect_files(CODE))
    unlabelled = [(p.smell, p.target) for p in preds if not any(_matches(p, l) for l in every)]
    assert unlabelled == []


def test_rules_have_full_recall_on_injected_smells():
    res = scan(load_config(), CODE, LABELS, use_slm=False)
    assert all(r["recall"] == 1.0 for r in res["scores"]["rules"].values() if r["positives"])


def test_slm_that_confirms_everything_equals_rules():
    res = scan(load_config(), CODE, LABELS, slm=FakeChatModel(_confirm_all))
    assert res["scores"]["rules+slm"] == res["scores"]["rules"]
    assert res["slm"]["calls"] == sum(1 for p in res["predictions"] if p["source"] == "gate")


def test_slm_that_rejects_everything_keeps_only_rule_smells():
    res = scan(load_config(), CODE, LABELS, slm=FakeChatModel(lambda *a: '{"findings": []}'))
    s = res["scores"]["rules+slm"]
    assert s["duplicated_logic"]["tp"] == 0 and s["magic_numbers"]["fp"] == 0
    assert s["long_method"]["tp"] == 1 and s["long_parameter_list"]["tp"] == 2


def test_multi_function_prompt_for_data_clumps():
    from smells.core.judges.judges import SmellJudges
    from smells.eval.scan import collect_files
    files = collect_files(CODE)
    preds, _ = predict(load_config(), files)
    clump = next(p for p in preds if p.smell == "data_clumps" and "room_free" in p.target)
    slm = FakeChatModel(lambda *a: '{"findings": []}')
    SmellJudges(slm).judge(clump.slm["hit"], files)
    prompt = slm.calls[0][0]["content"]
    assert "def schedule_class" in prompt and "def room_free" in prompt and "## Smell: data_clumps" in prompt


def test_unlabelled_scan_with_sampling_and_review_sheet(tmp_path):
    import csv
    sheet = tmp_path / "review.csv"
    res = scan(load_config(), CODE, None, slm=FakeChatModel(_confirm_all), include=["gymdesk"],
               max_per_smell=1, review_csv=sheet)
    assert all(b["candidates"] <= 1 for b in res["by_smell"].values())
    assert res["candidates_before_sampling"] > res["candidates"]
    rows = list(csv.DictReader(sheet.open()))
    assert len(rows) == res["candidates"] and all(r["code"] for r in rows)
    assert {r["slm_confirmed"] for r in rows if r["source"] == "gate"} == {"True"}
