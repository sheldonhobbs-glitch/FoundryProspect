"""Calendar events. Google Calendar is the source of truth; the local
calendar_events table is a read cache. Everything Google-specific stays in
the api.google_calendar adapter — callers here only see Ember concepts and
DomainErrors, so the provider can change without touching routes or tools."""

import logging
from datetime import date, datetime, time, timedelta

from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import google_calendar as gcal
from api.config import get_settings
from db.models import CalendarEvent
from domain.clock import household_tz
from domain.errors import IntegrationError, NotFound

logger = logging.getLogger("ember.domain.calendar")

OWNERS = ("shared", "sheldon", "partner")

# Supported repeat patterns -> RFC 5545 RRULE bodies.
RECURRENCE_RULES = {
    "daily": "FREQ=DAILY",
    "weekly": "FREQ=WEEKLY",
    "fortnightly": "FREQ=WEEKLY;INTERVAL=2",
    "monthly": "FREQ=MONTHLY",
}


def _service(db: Session):
    try:
        service = gcal.get_service(db)
    except gcal.CalendarError as exc:
        raise IntegrationError(str(exc)) from exc
    if service is None:
        raise IntegrationError("Google Calendar isn't connected yet.")
    return service


def get_event(db: Session, event_id: int) -> CalendarEvent:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise NotFound(f"No calendar event with id {event_id}.")
    return event


def list_events(db: Session, start: date | None = None, end: date | None = None) -> list[CalendarEvent]:
    """Events from the local cache. start/end are household-local dates,
    inclusive; either may be omitted."""
    tz = household_tz()
    stmt = select(CalendarEvent).order_by(CalendarEvent.start_time)
    if start is not None:
        stmt = stmt.where(CalendarEvent.end_time > datetime.combine(start, time.min, tzinfo=tz))
    if end is not None:
        stmt = stmt.where(
            CalendarEvent.start_time < datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz)
        )
    return list(db.scalars(stmt))


def _google_body(title: str, description: str | None, location: str | None,
                 start_time: datetime, end_time: datetime, all_day: bool,
                 recurrence: str | None = None, repeat_until: date | None = None) -> dict:
    body = gcal.event_to_google_body(title, description, location, start_time, end_time, all_day)
    if not all_day:
        # Google requires an explicit time zone on recurring timed events.
        tz_name = get_settings().household_timezone
        body["start"]["timeZone"] = tz_name
        body["end"]["timeZone"] = tz_name
    if recurrence:
        rule = RECURRENCE_RULES[recurrence]
        if repeat_until:
            rule += f";UNTIL={repeat_until.strftime('%Y%m%d')}"
        body["recurrence"] = [f"RRULE:{rule}"]
    return body


def create_event(
    db: Session, *, title: str, start_time: datetime, end_time: datetime, all_day: bool = False,
    location: str | None = None, description: str | None = None, owner: str = "shared",
    recurrence: str | None = None, repeat_until: date | None = None,
) -> CalendarEvent | None:
    """Creates the event in Google, then mirrors it locally. Returns the
    local row, or None for recurring events — those come back from Google as
    a series master, so the cache is refreshed via sync (which stores the
    expanded instances) rather than caching the master and duplicating the
    first occurrence."""
    if recurrence is not None and recurrence not in RECURRENCE_RULES:
        raise ValueError(f"Unsupported recurrence '{recurrence}'.")
    service = _service(db)
    body = _google_body(title, description, location, start_time, end_time, all_day, recurrence, repeat_until)
    try:
        g_event = service.events().insert(calendarId=get_settings().google_calendar_id, body=body).execute()
    except Exception as exc:
        logger.exception("Google Calendar event create failed")
        raise IntegrationError("Couldn't create the event in Google Calendar.") from exc

    if recurrence:
        try:
            gcal.sync_events(db)
        except gcal.CalendarError:
            logger.exception("post-create sync failed; the worker will catch up")
        for instance in db.scalars(
            select(CalendarEvent).where(CalendarEvent.google_event_id.startswith(g_event["id"] + "_"))
        ):
            instance.owner = owner
        db.flush()
        return None

    event = CalendarEvent(
        google_event_id=g_event["id"], title=title, description=description, location=location,
        start_time=start_time, end_time=end_time, all_day=all_day, owner=owner,
    )
    db.add(event)
    db.flush()
    return event


def update_event(db: Session, event: CalendarEvent, **changes) -> CalendarEvent:
    service = _service(db)
    for field, value in changes.items():
        setattr(event, field, value)
    body = _google_body(event.title, event.description, event.location,
                        event.start_time, event.end_time, event.all_day)
    try:
        service.events().update(
            calendarId=get_settings().google_calendar_id, eventId=event.google_event_id, body=body
        ).execute()
    except Exception as exc:
        logger.exception("Google Calendar event update failed")
        raise IntegrationError("Couldn't update the event in Google Calendar.") from exc
    db.flush()
    return event


def delete_event(db: Session, event: CalendarEvent) -> None:
    service = _service(db)
    try:
        service.events().delete(
            calendarId=get_settings().google_calendar_id, eventId=event.google_event_id
        ).execute()
    except HttpError as exc:
        # 404/410: already gone on Google's side — still clean up locally.
        if exc.resp.status not in (404, 410):
            logger.exception("Google Calendar event delete failed")
            raise IntegrationError("Couldn't delete the event in Google Calendar.") from exc
    except Exception as exc:
        logger.exception("Google Calendar event delete failed")
        raise IntegrationError("Couldn't delete the event in Google Calendar.") from exc
    db.delete(event)
    db.flush()
