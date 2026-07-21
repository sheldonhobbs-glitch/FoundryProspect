from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.auth import create_session_token, verify_login_token
from api.config import get_settings
from api.routes import auth as auth_routes
from api.routes import health as health_routes

app = FastAPI(title="Ember")
settings = get_settings()

app.include_router(health_routes.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api")

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("frontend/index.html")


@app.get("/login/{token}")
def magic_login(token: str) -> RedirectResponse:
    """The entire login flow: visiting this bookmarked URL with the right
    token sets the session cookie and sends you into the app. Wrong or
    missing token just bounces back to '/' still logged out."""
    response = RedirectResponse(url="/")
    if verify_login_token(token):
        response.set_cookie(
            key=settings.session_cookie_name,
            value=create_session_token(),
            max_age=settings.session_max_age_days * 24 * 60 * 60,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
        )
    return response


@app.get("/service-worker.js")
def service_worker() -> FileResponse:
    return FileResponse("frontend/service-worker.js", media_type="application/javascript")


@app.get("/manifest.json")
def manifest() -> FileResponse:
    return FileResponse("frontend/manifest.json", media_type="application/manifest+json")
