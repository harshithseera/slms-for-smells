"""One OpenAI-compatible chat client for every model (API LLMs and local Ollama SLMs).

Models are picked by *role* (codegen, judge_code, ...) from the config. Every call returns
token counts and wall-clock latency so runs can be compared on cost.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import httpx

from smells.config import api_key

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""


@dataclass
class ChatResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    model: str = ""
    raw_message: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)  # provider's raw usage block


class ChatModel(Protocol):
    name: str

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        json_mode: bool = False,
    ) -> ChatResult: ...


class OpenAICompatClient:
    """Minimal client for /v1/chat/completions (OpenAI, OpenRouter, Ollama, vLLM, ...)."""

    def __init__(self, model_cfg: dict[str, Any]):
        self.cfg = model_cfg
        self.name = model_cfg["model"]
        self.base_url = model_cfg["base_url"].rstrip("/")
        headers = {"Content-Type": "application/json"}
        key = api_key(model_cfg)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        self._http = httpx.Client(headers=headers, timeout=model_cfg.get("timeout_s", 600))

    RETRY_STATUS = {429, 500, 502, 503, 504}

    def _post_with_retry(self, body: dict) -> httpx.Response:
        """Retry rate limits and transient server errors with exponential backoff."""
        retries = self.cfg.get("max_retries", 5)
        self._waited = 0.0
        for attempt in range(retries + 1):
            try:
                resp = self._http.post(f"{self.base_url}/chat/completions", json=body)
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):  # not ConnectError: refused = no server, fail fast
                if attempt == retries:
                    raise
            else:
                if resp.status_code not in self.RETRY_STATUS or attempt == retries:
                    return resp
                wait = resp.headers.get("retry-after")
                if wait and wait.replace(".", "", 1).isdigit():
                    self._wait(min(float(wait), 120))
                    continue
            self._wait(min(2 ** attempt * self.cfg.get("retry_base_s", 2.0), 120))
        raise RuntimeError("unreachable")

    _sleep = staticmethod(time.sleep)

    def _wait(self, seconds: float) -> None:
        self._waited += seconds
        self._sleep(seconds)

    def chat(self, messages, tools=None, json_mode=False) -> ChatResult:
        body: dict[str, Any] = {
            "model": self.name,
            "messages": messages,
            "temperature": self.cfg.get("temperature", 0),
        }
        for k in ("seed", "max_tokens"):
            if self.cfg.get(k) is not None:
                body[k] = self.cfg[k]
        if tools:
            body["tools"] = tools
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        body.update(self.cfg.get("extra_body") or {})  # provider-specific, e.g. reasoning_effort
        t0 = time.perf_counter()
        resp = self._post_with_retry(body)
        latency = time.perf_counter() - t0 - self._waited  # backoff waits are not model latency
        if resp.is_error:
            raise httpx.HTTPStatusError(
                f"{resp.status_code} from {self.base_url} ({self.name}): {resp.text[:500]}",
                request=resp.request, response=resp,
            )
        data = resp.json()
        msg = data["choices"][0]["message"]
        usage = data.get("usage") or {}
        calls = []
        for tc in msg.get("tool_calls") or []:
            raw = tc["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(tc.get("id", ""), tc["function"]["name"], args, str(raw)))
        text = _THINK_RE.sub("", msg.get("content") or "").strip()
        return ChatResult(
            text=text,
            tool_calls=calls,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            latency_s=latency,
            model=data.get("model", self.name),
            raw_message=msg,
            usage=usage,
        )


class FakeChatModel:
    """Scripted model for tests: `responder(messages, tools, json_mode) -> ChatResult | str`."""

    def __init__(self, responder: Callable[..., ChatResult | str], name: str = "fake"):
        self.responder = responder
        self.name = name
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None, json_mode=False) -> ChatResult:
        self.calls.append([dict(m) for m in messages])
        out = self.responder(messages, tools, json_mode)
        if isinstance(out, str):
            out = ChatResult(text=out)
        out.model = out.model or self.name
        return out


def get_model(cfg: dict, role: str) -> ChatModel:
    return OpenAICompatClient(cfg["models"][role])
