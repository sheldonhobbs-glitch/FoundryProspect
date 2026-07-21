import base64
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql://ember:ember@localhost:5432/ember"

    secret_key: str = "dev-only-insecure-secret-key"
    session_max_age_days: int = 30
    session_cookie_name: str = "ember_session"

    household_username: str = "change-me"
    # Base64-encoded bcrypt hash. Base64 has no "$" characters, which avoids a
    # real footgun: raw bcrypt hashes (e.g. "$2b$12$...") get mangled by Docker
    # Compose's .env variable interpolation (it tries to expand "$something" as
    # a variable reference) while python-dotenv does not — the same .env file
    # would behave differently under `docker compose up` vs. bare `uvicorn`.
    household_password_hash_b64: str = ""

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

    @property
    def household_password_hash(self) -> str:
        if not self.household_password_hash_b64:
            return ""
        return base64.b64decode(self.household_password_hash_b64).decode("utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
