from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from db.models import Bill, MaintenanceItem, Recurrence, RecurrenceUnit
from domain import clock, household_admin, meals
from domain.errors import NotFound


def test_household_today_uses_household_timezone(monkeypatch):
    # 7pm UTC on the 29th is already 5am on the 30th in Cairns.
    fixed = datetime(2026, 9, 29, 19, 0, tzinfo=ZoneInfo("UTC"))

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz)

    monkeypatch.setattr(clock, "datetime", FrozenDatetime)
    assert clock.household_today() == date(2026, 9, 30)


def test_recurring_bill_rolls_forward_and_stays_unpaid(db):
    bill = Bill(name="Power", amount=312, due_date=date(2026, 9, 30), recurrence=Recurrence.monthly,
                category="utilities", paid=False)
    db.add(bill)
    household_admin.mark_bill_paid(db, bill)
    assert (bill.due_date, bill.paid) == (date(2026, 10, 30), False)


def test_one_off_bill_is_marked_paid(db):
    bill = Bill(name="Plumber", amount=180, due_date=date(2026, 9, 30), recurrence=Recurrence.one_time,
                category="home maintenance", paid=False)
    db.add(bill)
    household_admin.mark_bill_paid(db, bill)
    assert (bill.due_date, bill.paid) == (date(2026, 9, 30), True)


def test_maintenance_done_stamps_household_date_and_rolls_recurrence(db, monkeypatch):
    monkeypatch.setattr(household_admin, "household_today", lambda: date(2026, 9, 30))
    item = MaintenanceItem(task="Air con service", property_or_appliance="Lounge", next_due=date(2026, 9, 20),
                           recurrence_value=3, recurrence_unit=RecurrenceUnit.months)
    db.add(item)
    household_admin.mark_maintenance_done(db, item)
    assert (item.last_done, item.next_due) == (date(2026, 9, 30), date(2026, 12, 30))


def test_missing_records_raise_not_found(db):
    with pytest.raises(NotFound):
        household_admin.get_bill(db, 999999)


def test_meal_upsert_replaces_rather_than_duplicates(db):
    first = meals.set_meal(db, date(2026, 10, 1), "Tacos")
    second = meals.set_meal(db, date(2026, 10, 1), "Stir-fry")
    assert first.id == second.id and second.meal_text == "Stir-fry"


def test_pantry_add_is_case_insensitive_and_dedupes(db):
    meals.add_pantry_item(db, "Eggs")
    meals.add_pantry_item(db, "eggs ", low_stock=True)
    items = meals.list_pantry(db)
    assert [(i.name, i.low_stock) for i in items] == [("Eggs", True)]
    with pytest.raises(NotFound):
        meals.remove_pantry_item(db, "caviar")
