import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.config import get_settings

settings = get_settings()

SESSION_VALUE = "household"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="ember-session")


def verify_credentials(username: str, password: str) -> bool:
    if username != settings.household_username:
        return False
    if not settings.household_password_hash:
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), settings.household_password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_session_token() -> str:
    return _serializer().dumps(SESSION_VALUE)


def verify_session_token(token: str | None) -> bool:
    if not token:
        return False
    max_age_seconds = settings.session_max_age_days * 24 * 60 * 60
    try:
        value = _serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return False
    return value == SESSION_VALUE
