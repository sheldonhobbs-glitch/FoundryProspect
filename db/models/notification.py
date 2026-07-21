from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class PendingNotification(Base):
    """A due-date reminder queued by the worker. `sent` means "delivered to
    the household" through whatever channel is live: in-app display for now,
    a Web Push notification once Phase 6 wires up VAPID delivery.

    (resource_type, resource_id) lets the worker avoid re-queuing the same
    reminder every cycle while it's still unacknowledged.
    """

    __tablename__ = "pending_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(500))
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
