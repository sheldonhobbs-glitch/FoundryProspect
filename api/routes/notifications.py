from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import require_auth
from api.schemas import NotificationRead
from db.models import PendingNotification
from db.session import get_db

router = APIRouter(
    prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_auth)]
)


@router.get("", response_model=list[NotificationRead])
def list_notifications(db: Session = Depends(get_db)) -> list[PendingNotification]:
    stmt = (
        select(PendingNotification)
        .where(PendingNotification.sent.is_(False))
        .order_by(PendingNotification.created_at)
    )
    return list(db.scalars(stmt))


@router.post("/{notification_id}/dismiss", response_model=NotificationRead)
def dismiss_notification(notification_id: int, db: Session = Depends(get_db)) -> PendingNotification:
    notification = db.get(PendingNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.sent = True
    db.commit()
    db.refresh(notification)
    return notification
