"""Deterministic stand-ins for the model provider."""

import copy
from itertools import count

from brain.provider import ModelTurn, ProviderError, ToolCall, ToolResult, ToolSpec

_ids = count(1)


def text_turn(text: str, stop: str = "end_turn") -> ModelTurn:
    return ModelTurn(stop=stop, text=text, tool_calls=[], raw_content=[{"type": "text", "text": text}], model="fake")


def tool_turn(*calls: tuple[str, dict], stop: str = "tool_use") -> ModelTurn:
    tool_calls = [ToolCall(id=f"call_{next(_ids)}", name=name, input=args) for name, args in calls]
    raw = [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in tool_calls]
    return ModelTurn(stop=stop, text="", tool_calls=tool_calls, raw_content=raw, model="fake",
                     input_tokens=100, output_tokens=20)


class FakeProvider:
    """Replays a script of ModelTurns (or exceptions) and records what it was sent."""

    name = "fake"

    def __init__(self, script: list):
        self.script = list(script)
        self.requests: list[dict] = []

    def run_turn(self, *, system: str, messages: list[dict], tools: list[ToolSpec]) -> ModelTurn:
        self.requests.append({"system": system, "messages": copy.deepcopy(messages), "tools": tools})
        if not self.script:
            raise AssertionError("FakeProvider ran out of scripted turns")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def user_text_message(self, text: str) -> dict:
        return {"role": "user", "content": [{"type": "text", "text": text}]}

    def assistant_message(self, turn: ModelTurn) -> dict:
        return {"role": "assistant", "content": turn.raw_content}

    def tool_results_message(self, results: list[ToolResult]) -> dict:
        return {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
            for r in results
        ]}

    def message_text(self, message: dict) -> str:
        return "".join(b.get("text", "") for b in message["content"] if b.get("type") == "text").strip()


__all__ = ["FakeProvider", "ProviderError", "text_turn", "tool_turn"]
