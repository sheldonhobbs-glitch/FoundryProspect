"""Ember background worker.

Runs as a separate long-lived process (not inside the API request/response
cycle) and performs periodic checks — e.g. daily "due soon" bill/subscription/
maintenance/warranty scans that queue push notifications (added in Phase 1).

Phase 0: skeleton only. Confirms it can reach the database on a fixed
interval and logs a heartbeat so `docker compose up` shows the worker is
alive and wired to the same config/DB as the API.
"""

import logging
import time

from sqlalchemy import text

from api.config import get_settings
from db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
logger = logging.getLogger("ember.worker")

CHECK_INTERVAL_SECONDS = 60 * 60  # hourly; jobs below decide what's actually due


def run_due_checks() -> None:
    """Placeholder for Phase 1's bill/subscription/maintenance/warranty due-date scan."""
    settings = get_settings()
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info(
            "heartbeat ok (reminder_days_ahead=%s)", settings.reminder_days_ahead
        )
    except Exception:
        logger.exception("worker heartbeat failed to reach the database")
    finally:
        db.close()


def main() -> None:
    logger.info("Ember worker starting, checking every %ss", CHECK_INTERVAL_SECONDS)
    while True:
        run_due_checks()
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
