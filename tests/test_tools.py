"""The household tool catalog, driven through the orchestrator with a
scripted model so validation, gating and summaries are all exercised."""

import json
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import select

from api.config import get_settings
from brain.orchestrator import Orchestrator, confirm_pending_action
from brain.tools import Risk
from brain.tools.catalog import build_registry
from db.models import (
    Bill,
    BillingCycle,
    CalendarEvent,
    PantryItem,
    Recurrence,
    Reminder,
    ShoppingListItem,
    Subscription,
)
from domain import calendar as calendar_domain
from domain.clock import household_tz
from tests.fakes import FakeProvider, text_turn, tool_turn

TZ = household_tz()
NOW = datetime(2026, 9, 30, 8, 0, tzinfo=TZ)  # Wednesday


def call(db, name, args, member="sheldon", registry=None):
    """Runs one tool call through the orchestrator; returns (reply, parsed result, is_error)."""
    provider = FakeProvider([tool_turn((name, args)), text_turn("ok")])
    reply = Orchestrator(db, provider, registry or build_registry(), member, clock=lambda: NOW).handle_message("x")
    block = provider.requests[1]["messages"][-1]["content"][0]
    content = block["content"]
    return reply, (content if block["is_error"] else json.loads(content)), block["is_error"]


@pytest.fixture
def calendar_writes(monkeypatch):
    monkeypatch.setattr(get_settings(), "ember_calendar_writes_enabled", True)


# --- catalog integrity ------------------------------------------------------

def test_catalog_is_well_formed(calendar_writes):
    registry = build_registry()
    tools = registry.enabled_tools()
    assert len(tools) == 23
    for tool in tools:
        assert len(tool.description) > 20, tool.name
        json.dumps(tool.spec().input_schema)
        if tool.risk is Risk.CONFIRM:
            assert tool.describe is not None


def test_calendar_writes_are_off_by_default():
    registry = build_registry()
    names = {t.name for t in registry.enabled_tools()}
    assert "list_calendar_events" in names
    assert not {"create_calendar_event", "update_calendar_event", "delete_calendar_event"} & names


# --- bills ------------------------------------------------------------------

def test_mark_recurring_bill_paid(db):
    bill = Bill(name="Origin electricity", amount=312, due_date=date(2026, 9, 30),
                recurrence=Recurrence.monthly, category="utilities", paid=False)
    db.add(bill)
    db.commit()

    reply, result, _ = call(db, "mark_bill_paid", {"bill_id": bill.id})

    assert reply.actions[0].summary == "Marked Origin electricity ($312) as paid — next one's due Fri 30 Oct."
    assert result["next_due"] == "2026-10-30 (Fri)"


def test_list_bills_includes_overdue_and_skips_paid(db):
    db.add_all([
        Bill(name="Water", amount=90, due_date=date(2026, 9, 20), recurrence=Recurrence.one_time,
             category="utilities", paid=False),
        Bill(name="Rates", amount=500, due_date=date(2026, 12, 1), recurrence=Recurrence.one_time,
             category="utilities", paid=False),
        Bill(name="Old", amount=10, due_date=date(2026, 9, 29), recurrence=Recurrence.one_time,
             category="x", paid=True),
    ])
    db.commit()

    _, result, _ = call(db, "list_bills", {"due_within_days": 7})

    assert [(b["name"], b["overdue"]) for b in result["bills"]] == [("Water", True)]


def test_bad_date_is_rejected_by_validation(db):
    _, result, is_error = call(db, "create_bill", {"name": "Gas", "amount": 80, "due_date": "next tuesday"})
    assert is_error and "due_date" in result
    assert db.scalars(select(Bill)).all() == []


# --- subscriptions (confirm) --------------------------------------------------

def test_cancel_subscription_needs_confirmation(db):
    sub = Subscription(name="Netflix", cost=22.99, billing_cycle=BillingCycle.monthly,
                       renewal_date=date(2026, 10, 4), category="streaming", active=True)
    db.add(sub)
    db.commit()
    registry = build_registry()

    reply, result, _ = call(db, "cancel_subscription", {"subscription_id": sub.id}, registry=registry)

    assert result["status"] == "awaiting_user_confirmation"
    assert "won't cancel it with Netflix" in reply.pending[0].summary
    db.refresh(sub)
    assert sub.active is True

    confirm_pending_action(db, registry, reply.pending[0].id, "sheldon", clock=lambda: NOW)
    db.refresh(sub)
    assert sub.active is False


# --- shopping, pantry, meals, reminders ---------------------------------------

def test_shopping_list_add_dedupes_and_summarises(db):
    reply, _, _ = call(db, "add_to_shopping_list",
                       {"items": [{"name": "milk"}, {"name": "bananas"}, {"name": "bread"}]})
    assert reply.actions[0].summary == "Added milk, bananas and bread to the shopping list."

    call(db, "add_to_shopping_list", {"items": [{"name": "Milk", "quantity": "2L"}]})
    items = db.scalars(select(ShoppingListItem).order_by(ShoppingListItem.id)).all()
    assert [(i.name, i.quantity, i.added_by) for i in items] == [
        ("milk", "2L", "sheldon"), ("bananas", None, "sheldon"), ("bread", None, "sheldon")]


def test_check_off_reports_items_not_on_list(db):
    call(db, "add_to_shopping_list", {"items": [{"name": "eggs"}]})
    _, result, _ = call(db, "check_off_shopping_items", {"names": ["eggs", "caviar"]})
    assert result == {"ticked_off": ["eggs"], "not_on_list": ["caviar"]}


def test_update_pantry_adds_and_removes(db):
    db.add(PantryItem(name="Eggs", low_stock=False))
    db.commit()
    reply, result, _ = call(db, "update_pantry", {"add": [{"name": "Chicken"}], "remove": ["eggs", "unicorn"]})

    assert reply.actions[0].summary == "Pantry: added Chicken; removed Eggs."
    assert result["not_in_pantry"] == ["unicorn"]
    assert [p.name for p in db.scalars(select(PantryItem))] == ["Chicken"]


def test_meal_plan_round_trip_labels_weekdays(db):
    call(db, "set_meal", {"day": "2026-10-01", "meal": "Tacos"})
    _, result, _ = call(db, "get_meal_plan", {})
    assert result["dinners"] == [{"day": "2026-10-01 (Thu)", "meal": "Tacos"}]


def test_reminder_for_someone_else(db):
    reply, _, _ = call(db, "create_reminder",
                       {"text": "Call the pool guy", "due_date": "2026-10-01", "due_time": "09:30",
                        "for_member": "partner"})
    assert reply.actions[0].summary == "Reminder set for Partner: “Call the pool guy” for Thu 1 Oct at 9:30am."
    r = db.scalars(select(Reminder)).one()
    assert (r.for_member, r.created_by, r.due_time) == ("partner", "sheldon", time(9, 30))


def test_reminder_rejects_unknown_member(db):
    _, result, is_error = call(db, "create_reminder", {"text": "x", "for_member": "the dog"})
    assert is_error and "for_member" in result


# --- calendar -------------------------------------------------------------------

def _event(db, title, start, hours=1, owner="shared"):
    e = CalendarEvent(google_event_id=f"g-{title}", title=title, start_time=start,
                      end_time=start + timedelta(hours=hours), all_day=False, owner=owner)
    db.add(e)
    db.commit()
    return e


def test_list_events_uses_household_local_days(db):
    # 11pm Thursday in Cairns is 1pm Thursday UTC — must count as Thursday.
    _event(db, "Late one", datetime(2026, 10, 1, 23, 0, tzinfo=TZ))
    _event(db, "Friday brekkie", datetime(2026, 10, 2, 7, 0, tzinfo=TZ))

    _, result, _ = call(db, "list_calendar_events", {"start_date": "2026-10-01"})

    assert [(e["title"], e["day"], e["time"]) for e in result["events"]] == [
        ("Late one", "2026-10-01 (Thu)", "23:00-00:00")]


def test_list_events_range_is_capped(db):
    _, result, is_error = call(db, "list_calendar_events", {"start_date": "2026-01-01", "end_date": "2026-12-31"})
    assert is_error and "two months" in result


def test_create_weekly_event_builds_local_times(db, calendar_writes, monkeypatch):
    captured = {}

    def fake_create(db, **kwargs):
        captured.update(kwargs)
        return None  # recurring events come back via sync

    monkeypatch.setattr(calendar_domain, "create_event", fake_create)

    reply, _, _ = call(db, "create_calendar_event",
                       {"title": "Noah's swimming", "day": "2026-10-01", "start_time": "16:00", "repeat": "weekly"})

    assert captured["start_time"] == datetime(2026, 10, 1, 16, 0, tzinfo=TZ)
    assert captured["end_time"] == datetime(2026, 10, 1, 17, 0, tzinfo=TZ)
    assert captured["recurrence"] == "weekly" and captured["all_day"] is False
    assert reply.actions[0].summary == "Added “Noah's swimming” to the calendar for Thu 1 Oct at 4pm, repeating weekly."


def test_moving_an_event_needs_confirmation_and_keeps_duration(db, calendar_writes, monkeypatch):
    event = _event(db, "Soccer", datetime(2026, 10, 3, 9, 0, tzinfo=TZ), hours=2)
    applied = {}
    monkeypatch.setattr(calendar_domain, "update_event",
                        lambda db, ev, **changes: applied.update(changes) or ev)
    registry = build_registry()

    reply, _, _ = call(db, "update_calendar_event", {"event_id": event.id, "start_time": "10:00"}, registry=registry)

    assert reply.pending[0].summary == "Change “Soccer” (Sat 3 Oct 9am): move to Sat 3 Oct 10am?"
    assert applied == {}  # nothing touched Google yet

    confirm_pending_action(db, registry, reply.pending[0].id, "sheldon", clock=lambda: NOW)
    assert applied["start_time"] == datetime(2026, 10, 3, 10, 0, tzinfo=TZ)
    assert applied["end_time"] == datetime(2026, 10, 3, 12, 0, tzinfo=TZ)
