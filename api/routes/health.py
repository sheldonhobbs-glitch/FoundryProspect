from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import get_settings
from db.session import get_db
from domain.clock import household_now

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"status": "ok", "database": db_ok}


@router.get("/today")
def today() -> dict:
    """The household's date and time zone, so screens agree with the server
    even on a device set to another time zone."""
    now = household_now()
    return {"date": now.date().isoformat(), "timezone": get_settings().household_timezone}
