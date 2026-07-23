import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CashflowKind(str, enum.Enum):
    income = "income"
    expense = "expense"


class CashflowEntry(Base):
    """Manual income/expense logging — there's no bank feed. Receipts cover
    itemized purchases; this covers everything else (pay, cash spending)."""

    __tablename__ = "cashflow_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[CashflowKind] = mapped_column(Enum(CashflowKind, name="cashflow_kind"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    entry_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
