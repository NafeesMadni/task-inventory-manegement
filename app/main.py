from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis_fastapi import FastAPIRedis
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import DeviceAPI, UserAPI
from app.core.config import get_settings
from app.database.db import get_sessionmaker
from app.database.models.seed import create_initial_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    LocalSession = await get_sessionmaker()

    async with LocalSession() as _session:
        await create_initial_admin(_session)

    yield


app = FastAPI(title="Async Inventory Management System!", lifespan=lifespan)

# Add SessionMiddleware to enable session support
app.add_middleware(SessionMiddleware, secret_key=get_settings().SESSION_SECRET)

FastAPIRedis(app).lifespan().caching().rate_limiting()

BASE_DIR = Path(__file__).resolve().parent.parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/api/health")
async def health():
    """Return a message indicating that the application is responding."""
    return {"message": "I'm healthy!"}


app.include_router(UserAPI().router, prefix="/api/v1")
app.include_router(DeviceAPI().router, prefix="/api/v1")


# Frontend pages
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "static" / "dashboard.html")


@app.get("/devices", include_in_schema=False)
def devices():
    return FileResponse(BASE_DIR / "static" / "devices.html")


@app.get("/signup", include_in_schema=False)
def sign():
    return FileResponse(BASE_DIR / "static" / "signup.html")


@app.get("/signin", include_in_schema=False)
def signin():
    return FileResponse(BASE_DIR / "static" / "signin.html")


@app.get("/create-join-request", include_in_schema=False)
def create_join_request():
    return FileResponse(BASE_DIR / "static" / "create_join_request.html")
