from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_sessionmaker
from app.database.models import User, get_user_loading_options
from app.services import JWTProvider


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

    role = await session.scalar(select(User.role).where(User.id == user_id))

    # For already approved users of the system; Aka authroized users (Admin/Superisors/Developers)
    if role:
        user = await session.scalar(
            select(User)
            .options(*get_user_loading_options(role))
            .where(User.id == user_id)
        )
    else:
        # For users whose join request is either rejected or pending
        user = await session.get(User, user_id)

    if user is None:
        response.delete_cookie(key="access_token")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session, please login again.",
        )

    return user


GetCurrentUser = Annotated[User, Depends(get_current_user)]
