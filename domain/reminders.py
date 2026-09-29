"""Household reminders — lightweight to-dos with an optional due date/time."""

from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Reminder
from domain.errors import NotFound


def list_reminders(db: Session, include_done: bool = False) -> list[Reminder]:
    stmt = select(Reminder).order_by(Reminder.due_date.asc().nulls_last(), Reminder.due_time.asc().nulls_last(),
                                     Reminder.created_at)
    if not include_done:
        stmt = stmt.where(Reminder.done.is_(False))
    return list(db.scalars(stmt))


def due_on_or_before(db: Session, day: date) -> list[Reminder]:
    stmt = (
        select(Reminder)
        .where(Reminder.done.is_(False), Reminder.due_date.is_not(None), Reminder.due_date <= day)
        .order_by(Reminder.due_date, Reminder.due_time.asc().nulls_first())
    )
    return list(db.scalars(stmt))


def create_reminder(db: Session, *, text: str, due_date: date | None = None, due_time: time | None = None,
                    for_member: str | None = None, created_by: str | None = None) -> Reminder:
    reminder = Reminder(text=text.strip(), due_date=due_date, due_time=due_time,
                        for_member=for_member, created_by=created_by)
    db.add(reminder)
    db.flush()
    return reminder


def get_reminder(db: Session, reminder_id: int) -> Reminder:
    reminder = db.get(Reminder, reminder_id)
    if reminder is None:
        raise NotFound(f"No reminder with id {reminder_id}.")
    return reminder


def complete_reminder(db: Session, reminder: Reminder, now: datetime) -> Reminder:
    reminder.done, reminder.done_at = True, now
    db.flush()
    return reminder
