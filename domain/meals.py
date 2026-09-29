"""Meal plan and pantry."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import MealPlanEntry, PantryItem
from domain.clock import household_today
from domain.errors import NotFound

PLAN_WINDOW_PAST_DAYS = 1
PLAN_WINDOW_FUTURE_DAYS = 6


def list_plan(db: Session, start: date | None = None, end: date | None = None) -> list[MealPlanEntry]:
    today = household_today()
    start = start or today - timedelta(days=PLAN_WINDOW_PAST_DAYS)
    end = end or today + timedelta(days=PLAN_WINDOW_FUTURE_DAYS)
    stmt = (
        select(MealPlanEntry)
        .where(MealPlanEntry.plan_date >= start, MealPlanEntry.plan_date <= end)
        .order_by(MealPlanEntry.plan_date)
    )
    return list(db.scalars(stmt))


def set_meal(db: Session, plan_date: date, meal_text: str) -> MealPlanEntry:
    """Upsert: setting a meal for a date that already has one replaces it."""
    entry = db.scalars(select(MealPlanEntry).where(MealPlanEntry.plan_date == plan_date)).first()
    if entry is None:
        entry = MealPlanEntry(plan_date=plan_date, meal_text=meal_text)
        db.add(entry)
    else:
        entry.meal_text = meal_text
    db.flush()
    return entry


def list_pantry(db: Session) -> list[PantryItem]:
    return list(db.scalars(select(PantryItem).order_by(PantryItem.name)))


def find_pantry_item(db: Session, name: str) -> PantryItem | None:
    stmt = select(PantryItem).where(func.lower(PantryItem.name) == name.strip().lower())
    return db.scalars(stmt).first()


def add_pantry_item(db: Session, name: str, low_stock: bool = False) -> PantryItem:
    """Adding something already in the pantry updates it rather than
    creating a duplicate."""
    item = find_pantry_item(db, name)
    if item is None:
        item = PantryItem(name=name.strip(), low_stock=low_stock)
        db.add(item)
    else:
        item.low_stock = low_stock
    db.flush()
    return item


def remove_pantry_item(db: Session, name: str) -> PantryItem:
    item = find_pantry_item(db, name)
    if item is None:
        raise NotFound(f"'{name}' isn't in the pantry.")
    db.delete(item)
    db.flush()
    return item
