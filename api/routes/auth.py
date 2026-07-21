from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from api.auth import create_session_token, verify_credentials, verify_session_token
from api.config import get_settings
from api.deps import require_auth

router = APIRouter()
settings = get_settings()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response) -> dict:
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_session_token()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    return {"authenticated": verify_session_token(token)}


@router.get("/auth/ping", dependencies=[Depends(require_auth)])
def ping() -> dict:
    """Trivial authenticated route to sanity-check that session cookies protect API routes."""
    return {"ok": True}
