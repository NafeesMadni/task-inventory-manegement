from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_sessionmaker
from app.database.models import User
from app.services.auth_manager import JWTProvider


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Yield a database session and close it when the dependency exits."""
    LocalSession = await get_sessionmaker()

    async with LocalSession() as _session:
        yield _session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    request: Request, session: DBSession, response: Response
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired, please login again.",
        )

    payload = JWTProvider.decode_access_token(token)
    user_id = int(payload["sub"])

    user = await session.get(User, user_id)

    if user is None:
        response.delete_cookie(key="access_token")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session, please login again.",
        )

    return user


GetCurrentUser = Annotated[User, Depends(get_current_user)]
