from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Reminder(Base):
    """A lightweight to-do with an optional due date/time. `for_member` is
    who it's for (None = the whole household); stored as the identity key
    until household members become real records."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(500))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    for_member: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
