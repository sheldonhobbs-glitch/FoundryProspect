from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.auth import verify_session_token
from api.config import get_settings
from api.deps import IDENTITIES, IDENTITY_COOKIE, get_identity, require_auth
from api.schemas import IdentitySet

router = APIRouter()
settings = get_settings()


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.session_cookie_name)
    response.delete_cookie(IDENTITY_COOKIE)
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    return {"authenticated": verify_session_token(token)}


@router.get("/auth/ping", dependencies=[Depends(require_auth)])
def ping() -> dict:
    """Trivial authenticated route to sanity-check that session cookies protect API routes."""
    return {"ok": True}


@router.get("/auth/identity", dependencies=[Depends(require_auth)])
def read_identity(identity: str | None = Depends(get_identity)) -> dict:
    return {"identity": identity}


@router.post("/auth/identity", dependencies=[Depends(require_auth)])
def set_identity(payload: IdentitySet, response: Response) -> dict:
    if payload.name not in IDENTITIES:
        raise HTTPException(status_code=422, detail="Unknown identity")
    response.set_cookie(
        key=IDENTITY_COOKIE, value=payload.name,
        max_age=settings.session_max_age_days * 24 * 60 * 60,
        httponly=True, secure=settings.is_production, samesite="lax",
    )
    return {"identity": payload.name}
