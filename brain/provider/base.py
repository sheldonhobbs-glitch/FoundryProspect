"""Model-provider abstraction. The boundary is one model turn: the
orchestrator owns the loop, and tools/domain code never see provider types.

Conversation messages are provider-native dicts, stored and replayed
verbatim, so each provider also builds its own message shapes."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

StopReason = Literal["end_turn", "tool_use", "max_tokens", "refusal", "other"]


class ProviderError(Exception):
    """The model call failed (network, auth, rate limit, outage)."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


@dataclass
class ModelTurn:
    stop: StopReason
    text: str
    tool_calls: list[ToolCall]
    raw_content: list[dict]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    extra: dict = field(default_factory=dict)


class AIProvider(Protocol):
    name: str

    def run_turn(self, *, system: str, messages: list[dict], tools: list[ToolSpec]) -> ModelTurn: ...

    def user_text_message(self, text: str) -> dict: ...

    def assistant_message(self, turn: ModelTurn) -> dict: ...

    def tool_results_message(self, results: list[ToolResult]) -> dict: ...
