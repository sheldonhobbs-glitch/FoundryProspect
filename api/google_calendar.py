"""Google Calendar integration. Google Calendar is the source of truth:
event writes go straight to the Calendar API, and db.models.CalendarEvent is
just a local read cache kept fresh by the worker's periodic pull plus
immediate writes from the CRUD routes.

Every function here is expected to be called from code that catches
exceptions and degrades gracefully (log + skip / return an error response)
rather than let a Google API hiccup take down a request or the worker loop.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import Resource, build
from sqlalchemy.orm import Session

from api.config import get_settings
from db.models import CalendarEvent, GoogleCalendarCredential

logger = logging.getLogger("ember.google_calendar")

SYNC_WINDOW_PAST_DAYS = 7
SYNC_WINDOW_FUTURE_DAYS = 90

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


class CalendarError(Exception):
    """Raised for any Google Calendar failure that a caller should surface
    as a clean error rather than a stack trace."""


def build_flow(state: str | None = None) -> Flow:
    settings = get_settings()
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=settings.google_redirect_uri, state=state
    )


def fetch_account_email(credentials: Credentials) -> str | None:
    try:
        session = AuthorizedSession(credentials)
        resp = session.get("https://www.googleapis.com/oauth2/v2/userinfo", timeout=10)
        resp.raise_for_status()
        return resp.json().get("email")
    except Exception:
        logger.exception("failed to fetch Google account email (non-fatal)")
        return None


def save_credentials(db: Session, credentials: Credentials, email: str | None) -> None:
    existing = db.query(GoogleCalendarCredential).first()
    if existing:
        db.delete(existing)
        db.flush()
    db.add(
        GoogleCalendarCredential(
            refresh_token=credentials.refresh_token, google_account_email=email
        )
    )
    db.commit()


def is_connected(db: Session) -> bool:
    return db.query(GoogleCalendarCredential).first() is not None


def get_service(db: Session) -> Resource | None:
    """Returns a Calendar API client, or None if not connected. Raises
    CalendarError if connected but the stored credentials no longer work
    (e.g. access was revoked in Google) — callers should treat that as
    "needs to reconnect", not a crash."""
    settings = get_settings()
    cred = db.query(GoogleCalendarCredential).first()
    if cred is None:
        return None
    try:
        credentials = Credentials(
            token=None,
            refresh_token=cred.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        logger.exception("failed to build Google Calendar client")
        raise CalendarError("Could not connect to Google Calendar. Try reconnecting.") from exc


def _parse_event_time(value: dict) -> tuple[datetime, bool]:
    if "date" in value:
        d = date.fromisoformat(value["date"])
        return datetime.combine(d, time.min, tzinfo=timezone.utc), True
    return datetime.fromisoformat(value["dateTime"]), False


def to_google_time(when: datetime, all_day: bool) -> dict:
    if all_day:
        return {"date": when.date().isoformat()}
    return {"dateTime": when.isoformat()}


def event_to_google_body(title: str, description: str | None, location: str | None,
                          start_time: datetime, end_time: datetime, all_day: bool) -> dict:
    return {
        "summary": title,
        "description": description,
        "location": location,
        "start": to_google_time(start_time, all_day),
        "end": to_google_time(end_time, all_day),
    }


def sync_events(db: Session) -> int:
    """Pulls events from Google into the local cache. This is a full re-list
    of a rolling time window (past week to next ~3 months) rather than
    incremental syncToken-based sync — simpler, and plenty for a household
    calendar's event volume."""
    service = get_service(db)
    if service is None:
        return 0

    settings = get_settings()
    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=SYNC_WINDOW_PAST_DAYS)).isoformat()
    time_max = (now + timedelta(days=SYNC_WINDOW_FUTURE_DAYS)).isoformat()

    try:
        result = (
            service.events()
            .list(
                calendarId=settings.google_calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
            )
            .execute()
        )
    except Exception as exc:
        # Broad on purpose: googleapiclient raises HttpError for API-level
        # failures, but token refresh failures (revoked/expired access) raise
        # google.auth.exceptions.RefreshError instead — both need to degrade
        # gracefully rather than crash the worker loop or a request.
        logger.exception("Google Calendar sync failed")
        raise CalendarError("Google Calendar sync failed.") from exc

    count = 0
    for g_event in result.get("items", []):
        google_id = g_event["id"]
        if g_event.get("status") == "cancelled":
            db.query(CalendarEvent).filter_by(google_event_id=google_id).delete()
            continue

        start_time, start_all_day = _parse_event_time(g_event["start"])
        end_time, _ = _parse_event_time(g_event["end"])

        existing = db.query(CalendarEvent).filter_by(google_event_id=google_id).first()
        if existing is None:
            existing = CalendarEvent(google_event_id=google_id)
            db.add(existing)
        existing.title = g_event.get("summary") or "(no title)"
        existing.description = g_event.get("description")
        existing.location = g_event.get("location")
        existing.start_time = start_time
        existing.end_time = end_time
        existing.all_day = start_all_day
        count += 1

    db.commit()
    return count
