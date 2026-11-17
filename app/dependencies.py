from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.db import get_sessionmaker
from app.database.models import LoginHistory, User, get_user_loading_options
from app.services import JWTProvider
from app.services.auth_manager import TokenPurpose


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

    payload = JWTProvider.decode_token(token)

    try:
        user_id = int(payload["sub"])
        session_id = payload["jti"]

        if payload["purpose"] != TokenPurpose.ACCESS:
            raise TypeError

    except KeyError, TypeError, ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    login_history = await session.scalar(
        select(LoginHistory).where(
            LoginHistory.user_id == user_id,
            LoginHistory.session_id == session_id,
            LoginHistory.signed_out_at.is_(None),
        )
    )

    if not login_history:
        # Delete the already expired or revoked cookie
        response.delete_cookie(
            key="access_token",
            path="/",
            httponly=True,
            secure=True,
            samesite="lax",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked, please login again.",
        )

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


async def verify_turnstile(request: Request) -> None:
    token = request.headers.get("cf-turnstile-response")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Turnstile verification token.",
        )

    # Extract real client IP
    client_ip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For")
        or (request.client.host if request.client else None)
    )

    data = {
        "secret": get_settings().TURNSTILE_SECRET_KEY,
        "response": token,
    }

    if client_ip:
        data["remoteip"] = client_ip

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(get_settings().SITEVERIFY_URL, data=data)
            response.raise_for_status()
            result = response.json()

        except httpx.HTTPError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to CAPTCHA verification service.",
            )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "CAPTCHA verification failed.",
                "error_codes": result.get("error-codes", []),
            },
        )

    # Enforce hostname matching in production to prevent cross-domain token reuse
    # if result.get("hostname") != "inventory-task.fastapicloud.dev":
    #     raise HTTPException(status_code=403, detail="Invalid token hostname.")


VerifyTurnstile = Annotated[None, Depends(verify_turnstile)]
GetCurrentUser = Annotated[User, Depends(get_current_user)]
