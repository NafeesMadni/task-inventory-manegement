from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from redis_fastapi import RateLimitBackendDep
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.types import (
    LoginRequest,
    SignupRequest,
    SupervisorResponse,
    UserResponse,
)
from app.core.config import get_settings
from app.database.models import JoinRequest, JoinRequestStatus, User
from app.database.models.enums import UserRole
from app.dependencies import DBSession, GetCurrentUser
from app.services.auth_manager import AuthProvider, JWTProvider


class UserAPI:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/user", tags=["User Endpoint"])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/signup",
            endpoint=self.signup,
            methods=["POST"],
            response_model=UserResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/grant-access",
            endpoint=self.grant_access,
            methods=["GET"],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/supervisors",
            endpoint=self.fetch_supervisors,
            methods=["GET"],
            response_model=list[SupervisorResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/login",
            endpoint=self.login,
            methods=["POST"],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/me",
            endpoint=self.get_me,
            methods=["GET"],
            response_model=UserResponse,
            status_code=status.HTTP_200_OK,
        )

    async def signup(
        self, payload: SignupRequest, session: DBSession, response: Response
    ) -> UserResponse:
        existing_user = await session.scalar(
            select(User).where(
                or_(User.email == payload.email, User.username == payload.username)
            )
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or username already registered",
            )

        if payload.requested_role == UserRole.DEVELOPER and not payload.requested_from:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The 'requested_from' field is required when requesting the DEVELOPER role.",
            )

        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            username=payload.username,
            email=str(payload.email),
            hashed_password=AuthProvider.get_hashed_password(payload.password),
        )

        session.add(user)
        await session.flush()

        if payload.requested_from:
            request_from_user = await session.scalar(
                select(User).where(User.id == payload.requested_from)
            )
            if not request_from_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="The user you're requesting from not found.",
                )

        else:
            # first fetch Admin user from the database
            request_from_user = await session.scalar(
                select(User).where(User.role == "admin")
            )
            if not request_from_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Admin not found.",
                )

        join_request = JoinRequest(
            requested_role=payload.requested_role,
            requested_by=user.id,
            requested_from=request_from_user.id,
            request_note=payload.request_note,
        )

        session.add(join_request)

        await session.commit()
        await session.refresh(user)

        # Sent email notification to the requested_from user if the role is developer
        email = request_from_user.email  # noqa: F841

        access_token = JWTProvider.create_access_token(user.id)
        max_age = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            max_age=max_age,
            expires=max_age,
        )

        return UserResponse(id=user.id, username=user.username, email=user.email)

    async def grant_access(
        self,
        join_request_id: Annotated[int, Query(...)],
        grant: Annotated[bool, Query(...)],
        user: GetCurrentUser,
        session: DBSession,
    ) -> None:
        join_request = await session.scalar(
            select(JoinRequest)
            .options(selectinload(JoinRequest.requester))
            .where(JoinRequest.id == join_request_id)
        )
        if not join_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found, please try again.",
            )

        if join_request.requested_from != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to manage this request.",
            )
        if join_request.status != JoinRequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This request has already been processed.",
            )

        if grant:
            join_request.status = JoinRequestStatus.APPROVED
            join_request.requester.role = join_request.requested_role
        else:
            join_request.status = JoinRequestStatus.REJECTED

        await session.commit()

        # Notify the requester about the rejection/approval

    async def fetch_supervisors(
        self, session: DBSession, response: Response
    ) -> list[SupervisorResponse]:
        supervisors = await session.scalars(
            select(User).where(User.role == "supervisor")
        )
        response.status_code = status.HTTP_200_OK
        return [
            SupervisorResponse(id=supervisor.id, username=supervisor.username)
            for supervisor in supervisors
        ]

    async def login(
        self,
        payload: LoginRequest,
        request: Request,
        response: Response,
        session: DBSession,
        limiter: RateLimitBackendDep,
    ) -> dict[str, str]:

        address = request.client.host if request.client else ""
        key = f"login:{payload.email}:{address}"

        WINDOW = 900
        MAX_ATTEMPTS = 5

        state = await limiter.peek(key, limit=MAX_ATTEMPTS, window=WINDOW)

        if state.remaining == 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Try again later.",
                headers={"Retry-After": str(max(1, int(state.retry_after)))},
            )

        user = await session.scalar(
            select(User)
            .options(selectinload(User.join_requests))
            .where(User.email == str(payload.email))
        )

        if user is None or AuthProvider.check_password(
            payload.password, user.hashed_password
        ):
            # Count only failed authentication attempts
            result = await limiter.hit(key, limit=MAX_ATTEMPTS, window=WINDOW)

            if not result.allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Try again later.",
                    headers={"Retry-After": str(max(1, int(result.retry_after)))},
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        await limiter.reset(key)

        if user.role == None:
            join_req = user.join_requests
            if join_req.status == JoinRequestStatus.REJECTED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your access request was rejected.",
                )

            if join_req.status == JoinRequestStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your access request is still pending.",
                )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has no assigned role.",
            )

        max_age = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
        access_token = JWTProvider.create_access_token(user.id)

        response.set_cookie(
            key="access_token", value=access_token, max_age=max_age, expires=max_age
        )

        return {"message": "Login successful"}

    async def get_me(self, user: GetCurrentUser) -> UserResponse:

        return UserResponse(id=user.id, username=user.username, email=user.email)
