from fastapi import HTTPException, Request, status

from api.auth import verify_session_token
from api.config import get_settings

settings = get_settings()


def require_auth(request: Request) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if not verify_session_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
