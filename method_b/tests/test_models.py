import httpx
import pytest

from smells.core.models import OpenAICompatClient


def client(handler, **cfg):
    c = OpenAICompatClient({"base_url": "https://api.example/v1/", "model": "m", **cfg})
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_extra_body_is_sent_and_url_joined():
    seen = {}

    def handler(req):
        seen["url"], seen["body"] = str(req.url), req.read().decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>x</think>hi"}}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 1}})

    r = client(handler, extra_body={"reasoning_effort": "low"}).chat([{"role": "user", "content": "q"}])
    assert seen["url"] == "https://api.example/v1/chat/completions"
    assert '"reasoning_effort": "low"' in seen["body"] or '"reasoning_effort":"low"' in seen["body"]
    assert r.text == "hi" and r.tokens_in == 3


def test_api_error_message_is_kept():
    c = client(lambda req: httpx.Response(400, json={"error": {"message": "model not found"}}))
    with pytest.raises(httpx.HTTPStatusError, match="model not found"):
        c.chat([{"role": "user", "content": "q"}])


def test_retries_rate_limit_then_succeeds():
    replies = iter([httpx.Response(429, headers={"retry-after": "1"}), httpx.Response(503),
                    httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})])
    c = client(lambda req: next(replies))
    waits = []
    c._sleep = waits.append
    assert c.chat([{"role": "user", "content": "q"}]).text == "ok"
    assert waits == [1.0, 4.0]


def test_gives_up_after_max_retries():
    c = client(lambda req: httpx.Response(429), max_retries=2)
    c._sleep = lambda s: None
    with pytest.raises(httpx.HTTPStatusError, match="429"):
        c.chat([{"role": "user", "content": "q"}])
