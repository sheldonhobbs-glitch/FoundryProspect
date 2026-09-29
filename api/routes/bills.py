from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import BillCreate, BillRead, BillUpdate
from db.models import Bill
from db.session import get_db
from domain import household_admin

router = APIRouter(
    prefix="/bills", tags=["bills"], dependencies=[Depends(require_auth)]
)

def _get_or_404(db: Session, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


@router.get("", response_model=list[BillRead])
def list_bills(db: Session = Depends(get_db)) -> list[Bill]:
    return list(db.scalars(select(Bill).order_by(Bill.due_date)))


@router.post("", response_model=BillRead, status_code=201)
def create_bill(payload: BillCreate, db: Session = Depends(get_db)) -> Bill:
    bill = Bill(**payload.model_dump())
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/{bill_id}", response_model=BillRead)
def get_bill(bill_id: int, db: Session = Depends(get_db)) -> Bill:
    return _get_or_404(db, bill_id)


@router.patch("/{bill_id}", response_model=BillRead)
def update_bill(bill_id: int, payload: BillUpdate, db: Session = Depends(get_db)) -> Bill:
    bill = _get_or_404(db, bill_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(bill, field, value)
    db.commit()
    db.refresh(bill)
    return bill


@router.delete("/{bill_id}", status_code=204)
def delete_bill(bill_id: int, db: Session = Depends(get_db)) -> None:
    bill = _get_or_404(db, bill_id)
    db.delete(bill)
    db.commit()


@router.post("/{bill_id}/mark-paid", response_model=BillRead)
def mark_bill_paid(bill_id: int, db: Session = Depends(get_db)) -> Bill:
    """Marks paid. For recurring bills, also rolls due_date to the next
    occurrence and resets paid to False for that new cycle."""
    bill = household_admin.mark_bill_paid(db, _get_or_404(db, bill_id))
    db.commit()
    db.refresh(bill)
    return bill
