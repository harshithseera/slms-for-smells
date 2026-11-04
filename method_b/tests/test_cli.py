from smells.core.models import ChatResult, FakeChatModel, ToolCall
from smells.config import load_config
from smells.eval.run import check_models


def fakes(code_reply, judge_reply, judge_tokens=None):
    def judge(messages, tools, json_mode):
        n = judge_tokens if judge_tokens is not None else len(messages[0]["content"]) // 4
        return ChatResult(text=judge_reply, tokens_in=n)
    models = {"codegen": FakeChatModel(lambda *a: code_reply), "judge_code": FakeChatModel(judge)}
    return lambda cfg, role: models[role]


def test_check_models_ok():
    good = ChatResult(text="", tool_calls=[ToolCall("1", "write_file", {"path": "a.py", "content": "x = 1"})])
    assert check_models(load_config(), get=fakes(good, '{"findings": []}'))


def test_check_models_flags_missing_tool_call_and_bad_json():
    assert not check_models(load_config(), get=fakes(ChatResult(text="sure!"), '{"findings": []}'))
    good = ChatResult(text="", tool_calls=[ToolCall("1", "write_file", {})])
    assert not check_models(load_config(), get=fakes(good, "Here you go: none"))


def test_check_models_reports_connection_errors():
    def boom(cfg, role):
        raise ConnectionError("refused")
    assert not check_models(load_config(), get=boom)


def test_check_models_detects_truncated_judge_context():
    good = ChatResult(text="", tool_calls=[ToolCall("1", "write_file", {"path": "a.py", "content": "x = 1"})])
    assert not check_models(load_config(), get=fakes(good, '{"findings": []}', judge_tokens=2048))
