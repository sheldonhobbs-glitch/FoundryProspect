"""Shared formatting for tool results and summaries. Dates handed to the
model always carry their weekday so it never has to compute one."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from domain.clock import household_tz
from domain.household import MEMBERS

MAX_LIST_ITEMS = 60

# "household" means everyone; the rest are member keys.
MemberChoice = Literal[tuple([*MEMBERS, "household"])]


def iso_day(d: date) -> str:
    """For data given to the model: '2026-10-03 (Sat)'."""
    return f"{d.isoformat()} ({d:%a})"


def short_day(d: date) -> str:
    """For people: 'Sat 3 Oct'."""
    return f"{d:%a} {d.day} {d:%b}"


def clock_time(t: time) -> str:
    """'9am', '4:30pm'."""
    hour = t.hour % 12 or 12
    suffix = "am" if t.hour < 12 else "pm"
    return f"{hour}{suffix}" if t.minute == 0 else f"{hour}:{t.minute:02d}{suffix}"


def when_label(start: datetime, all_day: bool) -> str:
    local = start.astimezone(household_tz())
    if all_day:
        return short_day(local.date())
    return f"{short_day(local.date())} {clock_time(local.time())}"


def money(amount) -> str:
    value = Decimal(str(amount))
    return f"${value:,.0f}" if value == value.to_integral() else f"${value:,.2f}"


def join_names(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]
