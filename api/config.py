from functools import lru_cache

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

    google_client_id: str = ""
    google_client_secret: str = ""
    google_calendar_id: str = ""

    anthropic_api_key: str = ""

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""

    port: int = 8000

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
