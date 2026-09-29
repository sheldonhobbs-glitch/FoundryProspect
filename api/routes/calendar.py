import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import google_calendar as gcal
from api.config import get_settings
from api.deps import require_auth
from api.schemas import CalendarEventCreate, CalendarEventRead, CalendarEventUpdate, CalendarStatus
from db.models import CalendarEvent, GoogleCalendarCredential
from db.session import get_db
from domain import calendar
from domain.errors import IntegrationError

logger = logging.getLogger("ember.api.calendar")

router = APIRouter(prefix="/calendar", tags=["calendar"], dependencies=[Depends(require_auth)])
settings = get_settings()

STATE_COOKIE = "oauth_state"


def _get_or_404(db: Session, event_id: int) -> CalendarEvent:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/status", response_model=CalendarStatus)
def calendar_status(db: Session = Depends(get_db)) -> CalendarStatus:
    cred = db.query(GoogleCalendarCredential).first()
    return CalendarStatus(
        configured=settings.google_calendar_configured,
        connected=cred is not None,
        google_account_email=cred.google_account_email if cred else None,
        calendar_id=settings.google_calendar_id,
    )


@router.get("/connect")
def connect() -> RedirectResponse:
    if not settings.google_calendar_configured:
        raise HTTPException(
            status_code=400,
            detail="Google Calendar isn't configured yet — set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in .env first.",
        )
    state = secrets.token_urlsafe(24)
    flow = gcal.build_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true", state=state
    )
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key=STATE_COOKIE, value=state, max_age=600, httponly=True,
        secure=settings.is_production, samesite="lax",
    )
    return response


@router.get("/oauth/callback")
def oauth_callback(
    request: Request, code: str | None = None, state: str | None = None,
    error: str | None = None, db: Session = Depends(get_db),
) -> RedirectResponse:
    cookie_state = request.cookies.get(STATE_COOKIE)
    response = RedirectResponse(url="/")
    response.delete_cookie(STATE_COOKIE)

    if error or not code or not state or not cookie_state or state != cookie_state:
        logger.warning("Google OAuth callback rejected (error=%s, state_mismatch=%s)", error, state != cookie_state)
        return response

    try:
        flow = gcal.build_flow(state=state)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        email = gcal.fetch_account_email(credentials)
        gcal.save_credentials(db, credentials, email)
        gcal.sync_events(db)
    except Exception:
        logger.exception("Google Calendar OAuth exchange failed")

    return response


@router.post("/disconnect")
def disconnect(db: Session = Depends(get_db)) -> dict:
    db.query(GoogleCalendarCredential).delete()
    db.commit()
    return {"ok": True}


@router.post("/sync")
def sync_now(db: Session = Depends(get_db)) -> dict:
    try:
        count = gcal.sync_events(db)
    except gcal.CalendarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"synced": count}


@router.get("/events", response_model=list[CalendarEventRead])
def list_events(db: Session = Depends(get_db)) -> list[CalendarEvent]:
    return list(db.scalars(select(CalendarEvent).order_by(CalendarEvent.start_time)))


@router.post("/events", response_model=CalendarEventRead, status_code=201)
def create_event(payload: CalendarEventCreate, db: Session = Depends(get_db)) -> CalendarEvent:
    try:
        event = calendar.create_event(
            db, title=payload.title, start_time=payload.start_time, end_time=payload.end_time,
            all_day=payload.all_day, location=payload.location, description=payload.description,
            owner=payload.owner,
        )
    except IntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.commit()
    db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=CalendarEventRead)
def update_event(event_id: int, payload: CalendarEventUpdate, db: Session = Depends(get_db)) -> CalendarEvent:
    event = _get_or_404(db, event_id)
    try:
        calendar.update_event(db, event, **payload.model_dump(exclude_unset=True))
    except IntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> None:
    event = _get_or_404(db, event_id)
    try:
        calendar.delete_event(db, event)
    except IntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    db.commit()
