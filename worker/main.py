"""Ember background worker.

Runs as a separate long-lived process (not inside the API request/response
cycle), on two cadences:

- Every CALENDAR_SYNC_INTERVAL_SECONDS, pulls Google Calendar into the local
  event cache, so events added directly in Google (not via Ember) show up.
- Once a day, scans bills, subscriptions, maintenance items, and warranties
  for anything due within REMINDER_DAYS_AHEAD and queues a PendingNotification
  row for each. Actual delivery (Web Push via VAPID) is wired up in Phase 6 —
  for now these show up in-app via GET /api/notifications.
"""

import logging
import time
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api import google_calendar as gcal
from api.config import get_settings
from db.models import Bill, MaintenanceItem, PendingNotification, Subscription, Warranty
from db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
logger = logging.getLogger("ember.worker")

CALENDAR_SYNC_INTERVAL_SECONDS = 15 * 60


def _queue_if_new(db: Session, resource_type: str, resource_id: int, message: str) -> None:
    stmt = select(PendingNotification).where(
        PendingNotification.resource_type == resource_type,
        PendingNotification.resource_id == resource_id,
        PendingNotification.sent.is_(False),
    )
    if db.scalars(stmt).first() is not None:
        return
    db.add(
        PendingNotification(resource_type=resource_type, resource_id=resource_id, message=message)
    )
    logger.info("queued notification: %s", message)


def run_due_checks() -> None:
    settings = get_settings()
    horizon = date.today() + timedelta(days=settings.reminder_days_ahead)
    db = SessionLocal()
    try:
        for bill in db.scalars(select(Bill).where(Bill.paid.is_(False), Bill.due_date <= horizon)):
            _queue_if_new(
                db, "bill", bill.id,
                f"Bill '{bill.name}' (${bill.amount}) is due {bill.due_date.isoformat()}.",
            )

        for sub in db.scalars(
            select(Subscription).where(Subscription.active.is_(True), Subscription.renewal_date <= horizon)
        ):
            _queue_if_new(
                db, "subscription_renewal", sub.id,
                f"Subscription '{sub.name}' renews {sub.renewal_date.isoformat()} (${sub.cost}).",
            )

        for sub in db.scalars(
            select(Subscription).where(
                Subscription.active.is_(True),
                Subscription.cancel_by_date.is_not(None),
                Subscription.cancel_by_date <= horizon,
            )
        ):
            _queue_if_new(
                db, "subscription_cancel_by", sub.id,
                f"Cancel-by deadline for '{sub.name}' is {sub.cancel_by_date.isoformat()}.",
            )

        for item in db.scalars(
            select(MaintenanceItem).where(
                MaintenanceItem.next_due.is_not(None), MaintenanceItem.next_due <= horizon
            )
        ):
            _queue_if_new(
                db, "maintenance", item.id,
                f"Maintenance due: {item.task} ({item.property_or_appliance}) by {item.next_due.isoformat()}.",
            )

        for warranty in db.scalars(select(Warranty).where(Warranty.expiry_date <= horizon)):
            _queue_if_new(
                db, "warranty", warranty.id,
                f"Warranty expiring: {warranty.item} on {warranty.expiry_date.isoformat()}.",
            )

        db.commit()
        logger.info("due-date scan complete (horizon=%s)", horizon.isoformat())
    except Exception:
        db.rollback()
        logger.exception("worker due-date scan failed")
    finally:
        db.close()


def sync_calendar() -> None:
    db = SessionLocal()
    try:
        count = gcal.sync_events(db)
        if count:
            logger.info("calendar sync: %d event(s) refreshed", count)
    except gcal.CalendarError:
        logger.exception("calendar sync failed")
    except Exception:
        db.rollback()
        logger.exception("calendar sync failed unexpectedly")
    finally:
        db.close()


def main() -> None:
    logger.info(
        "Ember worker starting: calendar sync every %ss, due-date scan once daily",
        CALENDAR_SYNC_INTERVAL_SECONDS,
    )
    last_due_check: date | None = None
    while True:
        sync_calendar()

        today = date.today()
        if today != last_due_check:
            run_due_checks()
            last_due_check = today

        time.sleep(CALENDAR_SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
