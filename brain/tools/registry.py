"""The capability registry. A Tool bundles a validated input model, a
handler that calls into the domain layer, and a risk level. Risk is set
here, in code — the model can't change how an action is gated."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from brain.provider import ToolSpec


class Risk(StrEnum):
    READ = "read"          # runs immediately, changes nothing
    LOW = "low"            # runs immediately, easily reversible, reported back
    CONFIRM = "confirm"    # held as a PendingAction until a person approves


@dataclass(frozen=True)
class ToolContext:
    db: Session
    member: str | None
    now: datetime


@dataclass
class ToolOutcome:
    data: Any                   # JSON-serialisable result handed back to the model
    summary: str | None = None  # human-readable description of what changed


Handler = Callable[[ToolContext, BaseModel], ToolOutcome]
Describer = Callable[[ToolContext, BaseModel], str]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    risk: Risk
    handler: Handler
    # Required for CONFIRM tools: renders the approval prompt ("Cancel
    # Netflix ($22.99/month)?"). May raise DomainError if the target doesn't
    # exist, so nothing is queued for a record that isn't there.
    describe: Describer | None = None
    enabled: Callable[[], bool] = lambda: True

    def __post_init__(self):
        if self.risk is Risk.CONFIRM and self.describe is None:
            raise ValueError(f"Confirm-level tool '{self.name}' needs a describe function.")

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, _clean_schema(self.input_model.model_json_schema()))


def _clean_schema(node: Any) -> Any:
    """Drops Pydantic's 'title' keys — noise the model doesn't need."""
    if isinstance(node, dict):
        return {k: _clean_schema(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_clean_schema(v) for v in node]
    return node


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name '{tool.name}'.")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool | None:
        tool = self._tools.get(name)
        return tool if tool is not None and tool.enabled() else None

    def enabled_tools(self) -> list[Tool]:
        # Sorted so the tool list is byte-stable between requests (prompt cache).
        return [t for _, t in sorted(self._tools.items()) if t.enabled()]

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self.enabled_tools()]
