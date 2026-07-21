from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import MaintenanceItemCreate, MaintenanceItemRead, MaintenanceItemUpdate
from db.models import MaintenanceItem
from db.session import get_db

router = APIRouter(
    prefix="/maintenance", tags=["maintenance"], dependencies=[Depends(require_auth)]
)


def _get_or_404(db: Session, item_id: int) -> MaintenanceItem:
    item = db.get(MaintenanceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Maintenance item not found")
    return item


@router.get("", response_model=list[MaintenanceItemRead])
def list_maintenance(db: Session = Depends(get_db)) -> list[MaintenanceItem]:
    return list(db.scalars(select(MaintenanceItem).order_by(MaintenanceItem.next_due)))


@router.post("", response_model=MaintenanceItemRead, status_code=201)
def create_maintenance(payload: MaintenanceItemCreate, db: Session = Depends(get_db)) -> MaintenanceItem:
    item = MaintenanceItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}", response_model=MaintenanceItemRead)
def get_maintenance(item_id: int, db: Session = Depends(get_db)) -> MaintenanceItem:
    return _get_or_404(db, item_id)


@router.patch("/{item_id}", response_model=MaintenanceItemRead)
def update_maintenance(
    item_id: int, payload: MaintenanceItemUpdate, db: Session = Depends(get_db)
) -> MaintenanceItem:
    item = _get_or_404(db, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_maintenance(item_id: int, db: Session = Depends(get_db)) -> None:
    item = _get_or_404(db, item_id)
    db.delete(item)
    db.commit()


@router.post("/{item_id}/mark-done", response_model=MaintenanceItemRead)
def mark_maintenance_done(item_id: int, db: Session = Depends(get_db)) -> MaintenanceItem:
    """Sets last_done to today. next_due isn't auto-recomputed — there's no
    fixed recurrence for maintenance tasks, so it's edited by hand."""
    item = _get_or_404(db, item_id)
    item.last_done = date.today()
    db.commit()
    db.refresh(item)
    return item
