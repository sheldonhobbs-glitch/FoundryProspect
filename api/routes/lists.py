"""Shopping list and reminders for the UI. Creating items is done through
Ember itself; the screens only need to show and tick things off."""

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.deps import require_auth
from db.models import ShoppingListItem
from db.session import get_db
from domain import reminders, shopping
from domain.clock import household_now, household_today
from domain.errors import NotFound

router = APIRouter(tags=["lists"], dependencies=[Depends(require_auth)])


class ShoppingItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: str | None
    checked: bool


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    due_date: date | None
    due_time: time | None
    for_member: str | None
    done: bool
    created_at: datetime


@router.get("/shopping", response_model=list[ShoppingItemRead])
def list_shopping(db: Session = Depends(get_db)) -> list[ShoppingListItem]:
    return shopping.list_items(db)


@router.post("/shopping/{item_id}/check", response_model=ShoppingItemRead)
def check_shopping_item(item_id: int, db: Session = Depends(get_db)) -> ShoppingListItem:
    item = db.get(ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.checked, item.checked_at = True, household_now()
    db.commit()
    db.refresh(item)
    return item


@router.get("/reminders", response_model=list[ReminderRead])
def list_reminders(due_today: bool = False, db: Session = Depends(get_db)):
    if due_today:
        return reminders.due_on_or_before(db, household_today())
    return reminders.list_reminders(db)


@router.post("/reminders/{reminder_id}/complete", response_model=ReminderRead)
def complete_reminder(reminder_id: int, db: Session = Depends(get_db)):
    try:
        reminder = reminders.get_reminder(db, reminder_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    reminders.complete_reminder(db, reminder, household_now())
    db.commit()
    db.refresh(reminder)
    return reminder
