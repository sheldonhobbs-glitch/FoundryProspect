"""The shared shopping list."""

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.models import ShoppingListItem


def list_items(db: Session, include_checked: bool = False) -> list[ShoppingListItem]:
    stmt = select(ShoppingListItem).order_by(ShoppingListItem.checked, ShoppingListItem.created_at)
    if not include_checked:
        stmt = stmt.where(ShoppingListItem.checked.is_(False))
    return list(db.scalars(stmt))


def _find_unchecked(db: Session, name: str) -> ShoppingListItem | None:
    return db.scalars(
        select(ShoppingListItem).where(
            func.lower(ShoppingListItem.name) == name.strip().lower(),
            ShoppingListItem.checked.is_(False),
        )
    ).first()


def add_items(db: Session, items: list[tuple[str, str | None]], added_by: str | None) -> list[ShoppingListItem]:
    """Adds (name, quantity) pairs. Something already on the list isn't
    duplicated — its quantity is updated if a new one was given."""
    result = []
    for name, quantity in items:
        existing = _find_unchecked(db, name)
        if existing is not None:
            if quantity:
                existing.quantity = quantity
            result.append(existing)
            continue
        item = ShoppingListItem(name=name.strip(), quantity=quantity, added_by=added_by)
        db.add(item)
        result.append(item)
    db.flush()
    return result


def check_off(db: Session, names: list[str], now: datetime) -> tuple[list[ShoppingListItem], list[str]]:
    """Marks items as bought. Returns (checked items, names not on the list)."""
    checked, missing = [], []
    for name in names:
        item = _find_unchecked(db, name)
        if item is None:
            missing.append(name)
            continue
        item.checked, item.checked_at = True, now
        checked.append(item)
    db.flush()
    return checked, missing


def clear_checked(db: Session) -> int:
    result = db.execute(delete(ShoppingListItem).where(ShoppingListItem.checked.is_(True)))
    db.flush()
    return result.rowcount
