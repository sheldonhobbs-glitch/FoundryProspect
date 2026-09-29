import json
from datetime import datetime, timedelta

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from brain.orchestrator import (
    FALLBACK_REPLIES,
    EmberUnavailable,
    Orchestrator,
    cancel_pending_action,
    confirm_pending_action,
)
from brain.tools import Risk, Tool, ToolOutcome, ToolRegistry
from db.models import EmberConversation, EmberMessage, EmberPendingAction, EmberTrace, ShoppingListItem
from domain.clock import household_tz
from domain.errors import DomainError
from tests.fakes import FakeProvider, ProviderError, text_turn, tool_turn

NOW = datetime(2026, 9, 30, 7, 15, tzinfo=household_tz())


class ItemArgs(BaseModel):
    name: str


class NoArgs(BaseModel):
    pass


def _add_item(ctx, args):
    ctx.db.add(ShoppingListItem(name=args.name, added_by=ctx.member))
    ctx.db.flush()
    return ToolOutcome({"added": args.name}, summary=f"Added {args.name} to the shopping list.")


def _remove_item(ctx, args):
    item = ctx.db.scalars(select(ShoppingListItem).where(ShoppingListItem.name == args.name)).first()
    ctx.db.delete(item)
    ctx.db.flush()
    return ToolOutcome({"removed": args.name}, summary=f"Removed {args.name}.")


def _describe_remove(ctx, args):
    item = ctx.db.scalars(select(ShoppingListItem).where(ShoppingListItem.name == args.name)).first()
    if item is None:
        raise DomainError(f"'{args.name}' isn't on the list.")
    return f"Remove {args.name} from the shopping list?"


def _half_write_then_crash(ctx, args):
    ctx.db.add(ShoppingListItem(name="should-not-persist"))
    ctx.db.flush()
    raise RuntimeError("boom")


def _domain_fail(ctx, args):
    raise DomainError("No bill called that.")


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(Tool("count_items", "Count items.", NoArgs, Risk.READ,
                      lambda ctx, a: ToolOutcome({"count": 3})))
    reg.register(Tool("add_item", "Add an item.", ItemArgs, Risk.LOW, _add_item))
    reg.register(Tool("remove_item", "Remove an item.", ItemArgs, Risk.CONFIRM, _remove_item,
                      describe=_describe_remove))
    reg.register(Tool("crash", "Crashes.", NoArgs, Risk.LOW, _half_write_then_crash))
    reg.register(Tool("fail", "Fails cleanly.", NoArgs, Risk.LOW, _domain_fail))
    return reg


def run(db, registry, script, text="hello", member="sheldon", now=NOW, **kw):
    provider = FakeProvider(script)
    reply = Orchestrator(db, provider, registry, member, clock=lambda: now, **kw).handle_message(text)
    return reply, provider


def last_trace(db):
    return db.scalars(select(EmberTrace).order_by(EmberTrace.id.desc())).first()


def tool_results_sent(provider, request_index):
    """The tool_result blocks the orchestrator sent in a given model request."""
    return provider.requests[request_index]["messages"][-1]["content"]


# --- happy paths -------------------------------------------------------------

def test_read_tool_runs_and_reply_is_returned(db, registry):
    reply, provider = run(db, registry, [tool_turn(("count_items", {})), text_turn("You have 3 items.")])

    assert reply.text == "You have 3 items."
    assert reply.actions == [] and reply.pending == []
    assert json.loads(tool_results_sent(provider, 1)[0]["content"]) == {"count": 3}
    trace = last_trace(db)
    assert trace.outcome == "ok" and trace.rounds == 2
    assert trace.tools_executed == ["count_items"]


def test_low_risk_tool_changes_data_and_is_reported(db, registry):
    reply, _ = run(db, registry, [tool_turn(("add_item", {"name": "milk"})), text_turn("Added milk.")])

    assert db.scalars(select(ShoppingListItem.name)).all() == ["milk"]
    assert [a.summary for a in reply.actions] == ["Added milk to the shopping list."]
    assert db.scalars(select(ShoppingListItem.added_by)).first() == "sheldon"


def test_user_message_carries_date_and_speaker_context(db, registry):
    _, provider = run(db, registry, [text_turn("Hi!")], text="what's on?")

    first = provider.requests[0]["messages"][0]["content"][0]["text"]
    assert "Wednesday 30 September 2026, 7:15 am" in first
    assert "Speaking: Sheldon" in first
    assert first.endswith("what's on?")
    # The system prompt must not vary per request (it's the cached prefix).
    assert "2026" not in provider.requests[0]["system"]


def test_parallel_tool_calls_all_answered_in_one_message(db, registry):
    _, provider = run(db, registry, [
        tool_turn(("add_item", {"name": "milk"}), ("add_item", {"name": "bread"})),
        text_turn("Added both."),
    ])
    results = tool_results_sent(provider, 1)
    assert len(results) == 2 and not any(r["is_error"] for r in results)


# --- confirmation gating -----------------------------------------------------

def test_confirm_tool_is_held_not_executed(db, registry):
    db.add(ShoppingListItem(name="milk"))
    db.commit()

    reply, provider = run(db, registry, [
        tool_turn(("remove_item", {"name": "milk"})),
        text_turn("Want me to remove milk?"),
    ])

    assert db.scalars(select(ShoppingListItem.name)).all() == ["milk"]  # unchanged
    assert len(reply.pending) == 1 and reply.pending[0].summary == "Remove milk from the shopping list?"
    sent = json.loads(tool_results_sent(provider, 1)[0]["content"])
    assert sent["status"] == "awaiting_user_confirmation"
    action = db.get(EmberPendingAction, reply.pending[0].id)
    assert action.status == "pending" and action.tool_input == {"name": "milk"}
    assert last_trace(db).tools_gated == ["remove_item"]


def test_confirming_executes_the_stored_action(db, registry):
    db.add(ShoppingListItem(name="milk"))
    db.commit()
    reply, _ = run(db, registry, [tool_turn(("remove_item", {"name": "milk"})), text_turn("Confirm?")])

    result = confirm_pending_action(db, registry, reply.pending[0].id, "partner",
                                    provider=FakeProvider([]), clock=lambda: NOW + timedelta(minutes=1))

    assert result == "Removed milk."
    assert db.scalars(select(ShoppingListItem)).all() == []
    action = db.get(EmberPendingAction, reply.pending[0].id)
    assert (action.status, action.resolved_by) == ("executed", "partner")
    # The model will hear about it on the next turn.
    note = db.scalars(select(EmberMessage).where(EmberMessage.role == "app_note")).one()
    assert "confirmed" in note.content["content"][0]["text"]


def test_confirming_twice_is_rejected(db, registry):
    db.add(ShoppingListItem(name="milk"))
    db.commit()
    reply, _ = run(db, registry, [tool_turn(("remove_item", {"name": "milk"})), text_turn("Confirm?")])
    confirm_pending_action(db, registry, reply.pending[0].id, "sheldon", clock=lambda: NOW)

    with pytest.raises(DomainError):
        confirm_pending_action(db, registry, reply.pending[0].id, "sheldon", clock=lambda: NOW)


def test_expired_confirmation_cannot_execute(db, registry):
    db.add(ShoppingListItem(name="milk"))
    db.commit()
    reply, _ = run(db, registry, [tool_turn(("remove_item", {"name": "milk"})), text_turn("Confirm?")])

    with pytest.raises(DomainError, match="expired"):
        confirm_pending_action(db, registry, reply.pending[0].id, "sheldon",
                               clock=lambda: NOW + timedelta(hours=1))
    assert db.scalars(select(ShoppingListItem.name)).all() == ["milk"]
    assert db.get(EmberPendingAction, reply.pending[0].id).status == "expired"


def test_cancelling_leaves_data_alone(db, registry):
    db.add(ShoppingListItem(name="milk"))
    db.commit()
    reply, _ = run(db, registry, [tool_turn(("remove_item", {"name": "milk"})), text_turn("Confirm?")])

    cancel_pending_action(db, reply.pending[0].id, "sheldon", clock=lambda: NOW)

    assert db.scalars(select(ShoppingListItem.name)).all() == ["milk"]
    assert db.get(EmberPendingAction, reply.pending[0].id).status == "cancelled"


def test_confirm_for_missing_record_is_not_queued(db, registry):
    reply, provider = run(db, registry, [tool_turn(("remove_item", {"name": "ghost"})), text_turn("Not there.")])

    assert reply.pending == []
    result = tool_results_sent(provider, 1)[0]
    assert result["is_error"] and "isn't on the list" in result["content"]
    assert db.scalars(select(EmberPendingAction)).all() == []


# --- validation and failures -------------------------------------------------

def test_invalid_input_is_rejected_before_running(db, registry):
    _, provider = run(db, registry, [tool_turn(("add_item", {"nam": "milk"})), text_turn("Sorry.")])

    result = tool_results_sent(provider, 1)[0]
    assert result["is_error"] and "name" in result["content"]
    assert db.scalars(select(ShoppingListItem)).all() == []
    assert last_trace(db).tools_failed == ["add_item"]


def test_unknown_tool_is_rejected(db, registry):
    _, provider = run(db, registry, [tool_turn(("launch_rocket", {})), text_turn("Can't.")])
    assert tool_results_sent(provider, 1)[0]["is_error"]


def test_domain_error_is_reported_to_the_model(db, registry):
    _, provider = run(db, registry, [tool_turn(("fail", {})), text_turn("Couldn't find it.")])
    result = tool_results_sent(provider, 1)[0]
    assert result["is_error"] and result["content"] == "No bill called that."


def test_crashing_tool_rolls_back_its_partial_writes(db, registry):
    _, provider = run(db, registry, [tool_turn(("crash", {})), text_turn("Something went wrong.")])

    assert tool_results_sent(provider, 1)[0]["is_error"]
    assert db.scalars(select(ShoppingListItem)).all() == []


def test_runaway_loop_is_capped(db, registry):
    reply, provider = run(db, registry, [tool_turn(("count_items", {})) for _ in range(10)])

    assert reply.text == FALLBACK_REPLIES["limit"]
    assert len(provider.requests) == 6
    assert db.get(EmberConversation, reply.conversation_id).closed
    assert last_trace(db).outcome == "limit"


def test_refusal_never_runs_tools(db, registry):
    reply, _ = run(db, registry, [tool_turn(("add_item", {"name": "milk"}), stop="refusal")])

    assert reply.text == FALLBACK_REPLIES["refusal"]
    assert db.scalars(select(ShoppingListItem)).all() == []
    assert db.get(EmberConversation, reply.conversation_id).closed


def test_truncated_tool_call_is_not_run(db, registry):
    reply, _ = run(db, registry, [tool_turn(("add_item", {"name": "mi"}), stop="max_tokens")])
    assert reply.text == FALLBACK_REPLIES["truncated"]
    assert db.scalars(select(ShoppingListItem)).all() == []


def test_provider_failure_surfaces_cleanly_and_is_traced(db, registry):
    with pytest.raises(EmberUnavailable, match="busy"):
        run(db, registry, [ProviderError("The AI service is busy right now.")])
    assert last_trace(db).outcome == "provider_error"


def test_daily_limit_blocks_requests(db, registry):
    for _ in range(2):
        run(db, registry, [text_turn("ok")], daily_limit=2)
    with pytest.raises(EmberUnavailable, match="limit"):
        run(db, registry, [text_turn("ok")], daily_limit=2)


# --- conversations -----------------------------------------------------------

def test_follow_up_continues_the_same_conversation(db, registry):
    first, _ = run(db, registry, [text_turn("Hi Sheldon.")], text="hi")
    second, provider = run(db, registry, [text_turn("Sure.")], text="and another thing",
                           now=NOW + timedelta(minutes=5))

    assert second.conversation_id == first.conversation_id
    sent = provider.requests[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]


def test_idle_conversation_starts_fresh(db, registry):
    first, _ = run(db, registry, [text_turn("Hi.")])
    second, provider = run(db, registry, [text_turn("Hi again.")], now=NOW + timedelta(hours=2))

    assert second.conversation_id != first.conversation_id
    assert len(provider.requests[0]["messages"]) == 1


def test_members_have_separate_conversations(db, registry):
    a, _ = run(db, registry, [text_turn("Hi.")], member="sheldon")
    b, _ = run(db, registry, [text_turn("Hi.")], member="partner")
    assert a.conversation_id != b.conversation_id


def test_trace_stores_no_conversation_text(db, registry):
    run(db, registry, [tool_turn(("add_item", {"name": "secret-item"})), text_turn("Added.")],
        text="add secret-item")
    trace = last_trace(db)
    row = {c.name: getattr(trace, c.name) for c in EmberTrace.__table__.columns}
    assert "secret-item" not in json.dumps(row, default=str)
