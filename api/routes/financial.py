from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import (
    CashflowEntryCreate,
    CashflowEntryRead,
    ReceiptCreate,
    ReceiptRead,
    ReceiptUpdate,
)
from db.models import CashflowEntry, CashflowKind, Receipt, Warranty
from db.session import get_db

router = APIRouter(prefix="/financial", tags=["financial"], dependencies=[Depends(require_auth)])

WARRANTY_EXPIRING_WINDOW_DAYS = 30


def _get_receipt_or_404(db: Session, receipt_id: int) -> Receipt:
    receipt = db.get(Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.get("/receipts", response_model=list[ReceiptRead])
def list_receipts(db: Session = Depends(get_db)) -> list[Receipt]:
    return list(db.scalars(select(Receipt).order_by(Receipt.purchased_at.desc())))


@router.post("/receipts", response_model=ReceiptRead, status_code=201)
def create_receipt(payload: ReceiptCreate, db: Session = Depends(get_db)) -> Receipt:
    receipt = Receipt(**payload.model_dump())
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.patch("/receipts/{receipt_id}", response_model=ReceiptRead)
def update_receipt(receipt_id: int, payload: ReceiptUpdate, db: Session = Depends(get_db)) -> Receipt:
    receipt = _get_receipt_or_404(db, receipt_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(receipt, field, value)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.delete("/receipts/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)) -> None:
    receipt = _get_receipt_or_404(db, receipt_id)
    db.delete(receipt)
    db.commit()


@router.get("/cashflow", response_model=list[CashflowEntryRead])
def list_cashflow(db: Session = Depends(get_db)) -> list[CashflowEntry]:
    return list(db.scalars(select(CashflowEntry).order_by(CashflowEntry.entry_date.desc())))


@router.post("/cashflow", response_model=CashflowEntryRead, status_code=201)
def create_cashflow_entry(payload: CashflowEntryCreate, db: Session = Depends(get_db)) -> CashflowEntry:
    entry = CashflowEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/cashflow/{entry_id}", status_code=204)
def delete_cashflow_entry(entry_id: int, db: Session = Depends(get_db)) -> None:
    entry = db.get(CashflowEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


@router.get("/summary")
def financial_summary(
    view: str = Query("monthly", pattern="^(monthly|alltime)$"), db: Session = Depends(get_db)
) -> dict:
    today = date.today()
    receipts = list(db.scalars(select(Receipt)))
    entries = list(db.scalars(select(CashflowEntry)))
    warranties = list(db.scalars(select(Warranty)))

    if view == "monthly":
        receipts = [r for r in receipts if r.purchased_at.year == today.year and r.purchased_at.month == today.month]
        entries = [e for e in entries if e.entry_date.year == today.year and e.entry_date.month == today.month]

    income = sum((e.amount for e in entries if e.kind == CashflowKind.income), start=0)
    manual_expense = sum((e.amount for e in entries if e.kind == CashflowKind.expense), start=0)
    receipt_expense = sum((r.amount for r in receipts), start=0)
    expenses = manual_expense + receipt_expense

    expiring_cutoff = today + timedelta(days=WARRANTY_EXPIRING_WINDOW_DAYS)
    expiring_count = sum(1 for w in warranties if today <= w.expiry_date <= expiring_cutoff)

    return {
        "view": view,
        "income": float(income),
        "expenses": float(expenses),
        "net": float(income - expenses),
        "receipts_count": len(list(db.scalars(select(Receipt)))),
        "warranties_count": len(warranties),
        "warranties_expiring_count": expiring_count,
    }
