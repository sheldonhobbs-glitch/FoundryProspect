from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class MealPlanEntry(Base):
    """One planned meal per day — no separate lunch/dinner slots for now."""

    __tablename__ = "meal_plan_entries"
    __table_args__ = (UniqueConstraint("plan_date", name="uq_meal_plan_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_date: Mapped[date] = mapped_column(Date)
    meal_text: Mapped[str] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
