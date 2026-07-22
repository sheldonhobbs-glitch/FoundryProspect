import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class RecurrenceUnit(str, enum.Enum):
    days = "days"
    weeks = "weeks"
    months = "months"
    years = "years"


class MaintenanceItem(Base):
    __tablename__ = "maintenance_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    task: Mapped[str] = mapped_column(String(200))
    property_or_appliance: Mapped[str] = mapped_column(String(200))
    last_done: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Both null means "no recurrence" — next_due is edited by hand. When both
    # are set, marking the task done auto-advances next_due by this interval.
    recurrence_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recurrence_unit: Mapped[RecurrenceUnit | None] = mapped_column(
        Enum(RecurrenceUnit, name="maintenance_recurrence_unit"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
