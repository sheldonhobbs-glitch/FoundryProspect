from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql://ember:ember@localhost:5432/ember"

    secret_key: str = "dev-only-insecure-secret-key"
    session_max_age_days: int = 30
    session_cookie_name: str = "ember_session"

    # The entire login: a long random secret both partners bookmark as
    # /login/<token>. Whoever holds the link is logged in — no username,
    # password, or email service required.
    household_login_token: str = ""

    reminder_days_ahead: int = 3

    # "Today" for the household. The server runs in UTC; without this, dates
    # stamped between midnight and ~10am in Cairns land on the previous day.
    household_timezone: str = "Australia/Brisbane"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_calendar_id: str = "primary"
    # Must exactly match a redirect URI registered on the OAuth client in
    # Google Cloud Console, e.g. https://<railway-domain>/api/calendar/oauth/callback
    google_redirect_uri: str = "http://localhost:8000/api/calendar/oauth/callback"

    anthropic_api_key: str = ""

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""

    port: int = 8000

    @field_validator("google_calendar_id")
    @classmethod
    def _default_calendar_id(cls, v: str) -> str:
        # An explicit-but-blank GOOGLE_CALENDAR_ID in .env would otherwise
        # override the "primary" default, breaking every Calendar API call.
        return v or "primary"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def google_calendar_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
