from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Receipt(Base):
    """A manually-entered or (later) photo-scanned purchase record. Doubles
    as the expense side of the cashflow summary and can be linked from a
    Warranty as proof of purchase."""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    purchased_at: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
