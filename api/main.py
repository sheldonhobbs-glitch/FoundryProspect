from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import auth as auth_routes
from api.routes import health as health_routes

app = FastAPI(title="Ember")

app.include_router(health_routes.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api")

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("frontend/index.html")


@app.get("/service-worker.js")
def service_worker() -> FileResponse:
    return FileResponse("frontend/service-worker.js", media_type="application/javascript")


@app.get("/manifest.json")
def manifest() -> FileResponse:
    return FileResponse("frontend/manifest.json", media_type="application/manifest+json")
