from datetime import date, datetime
from zoneinfo import ZoneInfo

from api.config import get_settings


def household_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().household_timezone)


def household_now() -> datetime:
    return datetime.now(household_tz())


def household_today() -> date:
    return household_now().date()
