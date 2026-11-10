from types import SimpleNamespace

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis_fastapi.deps import get_rate_limit_backend
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.models import Base, User, UserRole
from app.dependencies import get_db_session
from app.main import app
from app.services.auth_manager import AuthProvider

TEST_DATABASE_URL = "sqlite+aiosqlite:///./tests/test.db"

engine = create_async_engine(TEST_DATABASE_URL)
TestingSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


class MockRateLimiter:
    async def peek(self, *args, **kwargs):
        return SimpleNamespace(
            remaining=5,
            retry_after=0,
        )

    async def hit(self, *args, **kwargs):
        return SimpleNamespace(
            allowed=True,
            retry_after=0,
        )

    async def reset(self, *args, **kwargs):
        pass


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db_session():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db_session] = override_get_db_session
app.dependency_overrides[get_rate_limit_backend] = MockRateLimiter


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver/api/v1",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def supervisor_user(db_session):
    supervisor = User(
        first_name="Test",
        last_name="Supervisor",
        username="test_supervisor",
        email="supervisor@example.com",
        hashed_password=AuthProvider.get_hashed_password("Password123!"),
        role=UserRole.SUPERVISOR,
    )

    db_session.add(supervisor)
    await db_session.commit()
    await db_session.refresh(supervisor)

    return supervisor
