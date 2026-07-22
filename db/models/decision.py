import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DecisionStatus(str, enum.Enum):
    open = "open"
    decided = "decided"


class Decision(Base):
    """A running list of things the household needs to decide. No voting or
    approval workflow — just item, notes, status, and the decision + date
    once it's resolved."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item: Mapped[str] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus, name="decision_status"), default=DecisionStatus.open
    )
    decision: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    decided_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
