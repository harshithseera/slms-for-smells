"""Shared code-generation loop: the LLM writes one unit (file) at a time via write_file.

The modes differ only in the `on_write` hook:
  - baseline: accepts the first write, no feedback
  - in_loop:  runs the monitor and returns findings as the tool result (bounded rounds)
Baseline and in-loop therefore see identical prompts, context and unit order.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from smells.core.design_parser import Project
from smells.core.models import ChatModel, ChatResult
from smells.core.runlog import RunLog
from smells.core.workspace import summarize_code

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write the complete contents of one source file of the project.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "file path relative to the project root"},
                "content": {"type": "string", "description": "the full Python source of the file"},
            },
            "required": ["path", "content"],
        },
    },
}

SYSTEM = """You are a senior Python engineer implementing a software project from its design documents.
Follow the design documents exactly: the file layout, module names, class names, function names,
signatures and behaviour they describe are what the project's users rely on.
Write clean, idiomatic, well-structured code. Use only the Python standard library and the
dependencies the documents mention.

You implement ONE file at a time. {io_rule}

=== DESIGN DOCUMENTS ===
{design}
"""

IO_TOOLS = "Write the file by calling the `write_file` tool with the full file content. Do not paste code in chat."
IO_TEXT = "Reply with the full file content in a single ```python code block and nothing else."

UNIT = """Implement `{path}` now.
All files to implement, in order: {all_files}.
{done}
Write the complete file `{path}`."""


@dataclass
class WriteOutcome:
    """What the on_write hook tells the loop."""
    message: str  # returned to the LLM as the tool result
    accept: bool  # True: unit is finished


@dataclass
class UnitResult:
    path: str
    code: str
    writes: int = 0
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    llm_s: float = 0.0
    gave_up: bool = False
    extra: dict = field(default_factory=dict)


_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(res: ChatResult, path: str) -> tuple[str | None, str | None]:
    """Return (code, tool_call_id) from a tool call or fenced block."""
    for tc in res.tool_calls:
        if tc.name == "write_file":
            content = tc.arguments.get("content")
            if isinstance(content, str) and content.strip():
                return content, tc.id
    blocks = _FENCE.findall(res.text or "")
    if blocks:
        return max(blocks, key=len), None
    return None, None


class UnitGenerator:
    def __init__(self, llm: ChatModel, project: Project, model_cfg: dict, log: RunLog, max_turns: int = 8):
        self.llm = llm
        self.project = project
        self.use_tools = model_cfg.get("use_tools", True)
        self.log = log
        self.max_turns = max_turns
        self.system = SYSTEM.format(io_rule=IO_TOOLS if self.use_tools else IO_TEXT, design=project.design_docs())

    def _context(self, written: dict[str, str]) -> str:
        if not written:
            return "No files have been written yet."
        return "Files already written (signatures only):\n" + "\n".join(
            summarize_code(p, c) for p, c in written.items()
        )

    def generate(
        self,
        path: str,
        written: dict[str, str],
        on_write: Callable[[str, int], WriteOutcome],
        extra_instructions: str = "",
    ) -> UnitResult:
        order = self.project.source_files()
        user = UNIT.format(path=path, all_files=", ".join(order), done=self._context(written))
        if extra_instructions:
            user += "\n\n" + extra_instructions
        messages: list[dict] = [{"role": "system", "content": self.system}, {"role": "user", "content": user}]
        ur = UnitResult(path=path, code="")
        nudged = False
        for _turn in range(self.max_turns):
            res = self.llm.chat(messages, tools=[WRITE_FILE_TOOL] if self.use_tools else None)
            ur.llm_calls += 1
            ur.tokens_in += res.tokens_in
            ur.tokens_out += res.tokens_out
            ur.llm_s += res.latency_s
            self.log.event(
                "llm_call", unit=path, role="codegen", model=res.model, tokens_in=res.tokens_in,
                tokens_out=res.tokens_out, latency_s=round(res.latency_s, 3), tool_calls=len(res.tool_calls),
                output_chars=len(res.text or "") + sum(len(c.raw_arguments or "") for c in res.tool_calls),
                usage=res.usage,
            )
            code, call_id = extract_code(res, path)
            assistant = {"role": "assistant", "content": res.text or ""}
            if res.tool_calls:
                assistant["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": tc.raw_arguments or json.dumps(tc.arguments)}}
                    for tc in res.tool_calls
                ]
            messages.append(assistant)
            if code is None:
                if ur.writes and not res.tool_calls:
                    break  # model says it's done after at least one write
                if nudged:
                    ur.gave_up = True
                    break
                nudged = True
                self._reply(messages, res, None, "You must write the file now. " + (IO_TOOLS if self.use_tools else IO_TEXT))
                continue
            ur.code = code
            ur.writes += 1
            outcome = on_write(code, ur.writes - 1)
            self._reply(messages, res, call_id, outcome.message)
            if outcome.accept:
                break
        return ur

    def _reply(self, messages: list[dict], res: ChatResult, call_id: str | None, text: str) -> None:
        if res.tool_calls:
            for tc in res.tool_calls:  # every tool call needs an answer
                msg = text if tc.id == call_id or call_id is None else "Ignored: write one file per call."
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": msg})
        else:
            messages.append({"role": "user", "content": text})
