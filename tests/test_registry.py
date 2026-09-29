import pytest
from pydantic import BaseModel, Field

from brain.tools import Risk, Tool, ToolOutcome, ToolRegistry


class Args(BaseModel):
    name: str = Field(description="What to add")
    qty: str | None = None


def _ok(ctx, args):
    return ToolOutcome({})


def test_confirm_tool_requires_describe():
    with pytest.raises(ValueError, match="describe"):
        Tool("cancel_thing", "Cancels.", Args, Risk.CONFIRM, _ok)


def test_duplicate_names_rejected():
    reg = ToolRegistry()
    reg.register(Tool("a", "A.", Args, Risk.READ, _ok))
    with pytest.raises(ValueError):
        reg.register(Tool("a", "A again.", Args, Risk.READ, _ok))


def test_specs_are_sorted_and_schema_is_clean():
    reg = ToolRegistry()
    reg.register(Tool("zeta", "Z.", Args, Risk.READ, _ok))
    reg.register(Tool("alpha", "A.", Args, Risk.READ, _ok))
    specs = reg.specs()

    assert [s.name for s in specs] == ["alpha", "zeta"]  # stable order keeps the prompt cache warm
    schema = specs[0].input_schema
    assert "title" not in str(schema)
    assert schema["required"] == ["name"]
    assert schema["properties"]["name"]["description"] == "What to add"


def test_disabled_tools_are_invisible_and_uncallable():
    reg = ToolRegistry()
    reg.register(Tool("create_event", "Create.", Args, Risk.LOW, _ok, enabled=lambda: False))
    assert reg.specs() == []
    assert reg.get("create_event") is None
