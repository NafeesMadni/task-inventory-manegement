import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_session = None
_init_lock = asyncio.Lock()


async def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory, locking its lazy initialization."""
    global _session

    if _session is not None:
        return _session

    async with _init_lock:
        if _session is not None:
            return _session

        engine = create_async_engine(get_settings().DATABASE_URL, echo=True)

        _session = async_sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )

    return _session
