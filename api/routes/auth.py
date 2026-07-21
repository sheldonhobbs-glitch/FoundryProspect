from fastapi import APIRouter, Depends, Request, Response

from api.auth import verify_session_token
from api.config import get_settings
from api.deps import require_auth

router = APIRouter()
settings = get_settings()


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
