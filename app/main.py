from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis_fastapi import FastAPIRedis

from app.api.v1.user_api import UserAPI

app = FastAPI(title="Async Inventory Management System!")

FastAPIRedis(app).lifespan().caching().rate_limiting()

BASE_DIR = Path(__file__).resolve().parent.parent

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)


app.include_router(UserAPI().router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Return a message indicating that the application is responding."""
    return {"message": "I'm healthy!"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")
