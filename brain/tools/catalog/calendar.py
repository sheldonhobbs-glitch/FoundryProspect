from datetime import date, datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from api import google_calendar as gcal
from api.config import get_settings
from brain.tools.catalog.common import MAX_LIST_ITEMS, clock_time, iso_day, short_day, when_label
from brain.tools.registry import Risk, Tool, ToolContext, ToolOutcome, ToolRegistry
from domain import calendar
from domain.clock import household_tz
from domain.errors import DomainError

Owner = Literal["shared", "sheldon", "partner"]
Repeat = Literal["daily", "weekly", "fortnightly", "monthly"]
MAX_RANGE_DAYS = 62


def _writes_enabled() -> bool:
    return get_settings().ember_calendar_writes_enabled


def _event_view(e) -> dict:
    tz = household_tz()
    start, end = e.start_time.astimezone(tz), e.end_time.astimezone(tz)
    view = {"id": e.id, "title": e.title, "day": iso_day(start.date()), "all_day": e.all_day, "owner": e.owner}
    if not e.all_day:
        view["time"] = f"{start:%H:%M}-{end:%H:%M}"
    if e.location:
        view["location"] = e.location
    return view


# --- list ---------------------------------------------------------------

class ListEventsArgs(BaseModel):
    start_date: date = Field(description="First day to include (YYYY-MM-DD, household local).")
    end_date: date | None = Field(None, description="Last day to include. Defaults to start_date.")


def list_events(ctx: ToolContext, a: ListEventsArgs) -> ToolOutcome:
    end = a.end_date or a.start_date
    if end < a.start_date:
        raise DomainError("end_date is before start_date.")
    if (end - a.start_date).days > MAX_RANGE_DAYS:
        raise DomainError("Ask about at most two months at a time.")
    events = calendar.list_events(ctx.db, a.start_date, end)
    return ToolOutcome({
        "events": [_event_view(e) for e in events[:MAX_LIST_ITEMS]],
        "truncated": len(events) > MAX_LIST_ITEMS,
        "calendar_connected": gcal.is_connected(ctx.db),
    })


# --- create -------------------------------------------------------------

class CreateEventArgs(BaseModel):
    title: str = Field(description="Short event title, e.g. \"Noah's swimming\".")
    day: date = Field(description="Date of the (first) event.")
    start_time: time | None = Field(None, description="Local start time, HH:MM. Omit for an all-day event.")
    end_time: time | None = Field(None, description="Local end time, HH:MM. Defaults to one hour after start.")
    location: str | None = None
    owner: Owner = Field("shared", description="Whose event: shared, sheldon or partner.")
    repeat: Repeat | None = Field(None, description="Repeat pattern, if it recurs.")
    repeat_until: date | None = Field(None, description="Last date a repeating event occurs, if known.")


def _span(day: date, start: time | None, end: time | None) -> tuple[datetime, datetime, bool]:
    tz = household_tz()
    if start is None:
        begin = datetime.combine(day, time.min, tzinfo=tz)
        return begin, begin + timedelta(days=1), True
    begin = datetime.combine(day, start, tzinfo=tz)
    finish = datetime.combine(day, end, tzinfo=tz) if end else begin + timedelta(hours=1)
    if finish <= begin:
        raise DomainError("The end time must be after the start time.")
    return begin, finish, False


def create_event(ctx: ToolContext, a: CreateEventArgs) -> ToolOutcome:
    start, end, all_day = _span(a.day, a.start_time, a.end_time)
    event = calendar.create_event(
        ctx.db, title=a.title, start_time=start, end_time=end, all_day=all_day,
        location=a.location, owner=a.owner, recurrence=a.repeat, repeat_until=a.repeat_until,
    )
    when = short_day(a.day) + ("" if all_day else f" at {clock_time(a.start_time)}")
    repeat = f", repeating {a.repeat}" if a.repeat else ""
    return ToolOutcome(
        {"created": True, "id": event.id if event else None},
        summary=f"Added “{a.title}” to the calendar for {when}{repeat}.",
    )


# --- update / delete (confirm) --------------------------------------------

class UpdateEventArgs(BaseModel):
    event_id: int
    title: str | None = None
    day: date | None = Field(None, description="New date, keeping the same time unless given.")
    start_time: time | None = Field(None, description="New local start time, HH:MM.")
    end_time: time | None = Field(None, description="New local end time, HH:MM.")
    location: str | None = None


def _updated_span(event, a: UpdateEventArgs) -> tuple[datetime, datetime] | None:
    if a.day is None and a.start_time is None and a.end_time is None:
        return None
    tz = household_tz()
    old_start, old_end = event.start_time.astimezone(tz), event.end_time.astimezone(tz)
    day = a.day or old_start.date()
    if event.all_day and a.start_time is None:
        begin = datetime.combine(day, time.min, tzinfo=tz)
        return begin, begin + (old_end - old_start)
    start = datetime.combine(day, a.start_time or old_start.time(), tzinfo=tz)
    end = datetime.combine(day, a.end_time, tzinfo=tz) if a.end_time else start + (old_end - old_start)
    if end <= start:
        raise DomainError("The end time must be after the start time.")
    return start, end


def _update_changes(ctx: ToolContext, a: UpdateEventArgs) -> tuple[object, dict]:
    event = calendar.get_event(ctx.db, a.event_id)
    changes: dict = {}
    if a.title:
        changes["title"] = a.title
    if a.location is not None:
        changes["location"] = a.location
    span = _updated_span(event, a)
    if span:
        changes["start_time"], changes["end_time"] = span
        if event.all_day and a.start_time is not None:
            changes["all_day"] = False
    if not changes:
        raise DomainError("Nothing to change.")
    return event, changes


def describe_update(ctx: ToolContext, a: UpdateEventArgs) -> str:
    event, changes = _update_changes(ctx, a)
    parts = []
    if "title" in changes:
        parts.append(f"rename to “{changes['title']}”")
    if "start_time" in changes:
        parts.append(f"move to {when_label(changes['start_time'], changes.get('all_day', event.all_day))}")
    if "location" in changes:
        parts.append(f"set location to {changes['location'] or 'none'}")
    return f"Change “{event.title}” ({when_label(event.start_time, event.all_day)}): {', '.join(parts)}?"


def update_event(ctx: ToolContext, a: UpdateEventArgs) -> ToolOutcome:
    event, changes = _update_changes(ctx, a)
    calendar.update_event(ctx.db, event, **changes)
    return ToolOutcome({"updated": True}, summary=f"Updated “{event.title}” — now {when_label(event.start_time, event.all_day)}.")


class DeleteEventArgs(BaseModel):
    event_id: int


def describe_delete(ctx: ToolContext, a: DeleteEventArgs) -> str:
    event = calendar.get_event(ctx.db, a.event_id)
    return f"Delete “{event.title}” ({when_label(event.start_time, event.all_day)}) from the calendar?"


def delete_event(ctx: ToolContext, a: DeleteEventArgs) -> ToolOutcome:
    event = calendar.get_event(ctx.db, a.event_id)
    label = f"“{event.title}” ({when_label(event.start_time, event.all_day)})"
    calendar.delete_event(ctx.db, event)
    return ToolOutcome({"deleted": True}, summary=f"Deleted {label} from the calendar.")


def register(registry: ToolRegistry) -> None:
    registry.register(Tool(
        "list_calendar_events",
        "List household calendar events between two dates. Call this whenever someone asks what's on, "
        "what's happening on a day or weekend, whether someone is free, or when an event is. Also use it to "
        "find an event's id before changing or deleting it.",
        ListEventsArgs, Risk.READ, list_events,
    ))
    registry.register(Tool(
        "create_calendar_event",
        "Add an event to the household calendar, optionally repeating (e.g. \"swimming every Thursday at 4pm\" "
        "-> repeat weekly). Use for appointments, activities and plans with a date.",
        CreateEventArgs, Risk.LOW, create_event, enabled=_writes_enabled,
    ))
    registry.register(Tool(
        "update_calendar_event",
        "Change an existing calendar event's title, date, time or location. Find its id first with "
        "list_calendar_events. Needs the user's confirmation.",
        UpdateEventArgs, Risk.CONFIRM, update_event, describe=describe_update, enabled=_writes_enabled,
    ))
    registry.register(Tool(
        "delete_calendar_event",
        "Remove an event from the household calendar. Find its id first with list_calendar_events. "
        "Needs the user's confirmation.",
        DeleteEventArgs, Risk.CONFIRM, delete_event, describe=describe_delete, enabled=_writes_enabled,
    ))
