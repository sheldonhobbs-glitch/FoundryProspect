from fastapi import HTTPException, Request, status

from api.auth import verify_session_token
from api.config import get_settings

settings = get_settings()

IDENTITY_COOKIE = "ember_identity"
IDENTITIES = ("sheldon", "partner")


def require_auth(request: Request) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if not verify_session_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )


def get_identity(request: Request) -> str | None:
    """Who's using the app right now (Sheldon or Partner) — plain attribution
    for votes/calendar ownership, not a security boundary. The real
    authentication is the shared session cookie from require_auth."""
    value = request.cookies.get(IDENTITY_COOKIE)
    return value if value in IDENTITIES else None
