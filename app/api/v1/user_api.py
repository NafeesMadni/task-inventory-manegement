from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from redis_fastapi import RateLimitBackendDep
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.types import (
    JoinRequestsResponse,
    LoginHistoryResponse,
    LoginRequest,
    SignupRequest,
    StatusResponse,
    SupervisorResponse,
    UserResponse,
)
from app.core.config import get_settings
from app.database.models import (
    JoinRequest,
    JoinRequestStatus,
    LoginHistory,
    SupervisorDeveloper,
    User,
    UserRole,
)
from app.dependencies import DBSession, GetCurrentUser
from app.services import AuthProvider, EmailManager, JWTProvider


class UserAPI:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/user", tags=["User Endpoint"])
        self._register_routes()
        self.email_manager = EmailManager()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/signup",
            endpoint=self.signup,
            methods=["POST"],
            response_model=UserResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/me",
            endpoint=self.get_me,
            methods=["get"],
            response_model=UserResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/join-requests",
            endpoint=self.get_join_requests,
            methods=["GET"],
            response_model=list[JoinRequestsResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/process-join-request",
            endpoint=self.process_join_request,
            methods=["GET"],
            response_model=StatusResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/supervisors",
            endpoint=self.active_supervisors,
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
            "/login-history",
            endpoint=self.get_users_login_history,
            methods=["GET"],
            response_model=list[LoginHistoryResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/logout",
            endpoint=self.logout,
            methods=["POST"],
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
            requested_from_user = await session.scalar(
                select(User).where(User.id == payload.requested_from)
            )
            if not requested_from_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="The user you're requesting from not found.",
                )

        else:
            # first fetch Admin user from the database
            requested_from_user = await session.scalar(
                select(User).where(User.role == "admin")
            )
            if not requested_from_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Admin not found.",
                )

        join_request = JoinRequest(
            requested_role=payload.requested_role,
            requested_by=user.id,
            requested_from=requested_from_user.id,
            request_note=payload.request_note,
        )

        session.add(join_request)

        await session.commit()
        await session.refresh(user)

        # Sent email notification to the requested_from user if the role is developer
        await self.email_manager.send_join_request_notification(
            to_email=requested_from_user.email,
            approver_username=requested_from_user.username,
            requester_username=user.username,
            requester_name=f"{user.first_name} {user.last_name}",
            requester_email=user.email,
            requested_role=join_request.requested_role.value,
            requested_at=join_request.created_at,
        )

        access_token = JWTProvider.create_access_token(user.id)
        max_age = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            max_age=max_age,
            expires=max_age,
        )

        return UserResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            role=user.role,
            email=user.email,
        )

    async def active_supervisors(self, session: DBSession) -> list[SupervisorResponse]:
        result = await session.execute(
            select(User.id, User.username).where(User.role == UserRole.SUPERVISOR)
        )
        supervisors = result.all()
        return [
            SupervisorResponse(id=supervisor.id, username=supervisor.username)
            for supervisor in supervisors
        ]

    async def get_join_requests(
        self, user: GetCurrentUser, session: DBSession, response: Response
    ) -> list[JoinRequestsResponse]:

        if user.role == UserRole.ADMIN:
            # Admin can see all join requests
            result = await session.scalars(select(JoinRequest))
            join_requests = result.all()

        elif user.role == UserRole.SUPERVISOR:
            # Supervisor can see requests addressed to them
            join_requests = user.received_join_requests

        else:
            response.status_code = status.HTTP_403_FORBIDDEN
            return []

        return [
            JoinRequestsResponse(
                id=jr.id,
                requested_role=jr.requested_role,
                requested_by=jr.requested_by,
                requested_from=jr.requested_from,
                request_note=jr.request_note or "",
                status=jr.status,
                requested_at=jr.created_at,
                processed_by=jr.processed_by,
                processed_at=jr.processed_at,
                processed_reason=jr.processed_reason,
            )
            for jr in join_requests
        ]

    async def process_join_request(
        self,
        join_request_id: Annotated[int, Query(...)],
        grant: Annotated[bool, Query(...)],
        user: GetCurrentUser,
        session: DBSession,
        response: Response,
        reason: Annotated[str | None, Query()] = None,
    ) -> StatusResponse:

        join_request = await session.scalar(
            select(JoinRequest)
            .options(
                selectinload(JoinRequest.requester),
                selectinload(JoinRequest.requested_from_user),
            )
            .where(JoinRequest.id == join_request_id)
        )

        if not join_request:
            response.status_code = status.HTTP_404_NOT_FOUND
            return StatusResponse(
                message="Request not found, please try again.",
            )

        if join_request.requested_role == UserRole.ADMIN:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(message="Invalid requested role.")

        if join_request.requested_from != user.id:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(
                message="You are not authorized to manage this request.",
            )

        if join_request.status != JoinRequestStatus.PENDING:
            return StatusResponse(
                message=f"This request has already been {join_request.status.value.lower()}."
            )

        requester = join_request.requester
        approver = join_request.requested_from_user

        if grant:
            if (
                approver.role == UserRole.SUPERVISOR
                and join_request.requested_role == UserRole.DEVELOPER
            ):
                supervisor_developer = SupervisorDeveloper(
                    supervisor_id=approver.id,
                    developer_id=requester.id,
                )
                session.add(supervisor_developer)

            requester.role = join_request.requested_role

        join_request.status = (
            JoinRequestStatus.APPROVED if grant else JoinRequestStatus.REJECTED
        )

        join_request.processed_by = user.id
        join_request.processed_at = datetime.now(UTC)
        join_request.processed_reason = (
            reason.strip() if reason and reason.strip() else None
        )

        await session.commit()

        # Notify the requester about the rejection/approval
        await self.email_manager.send_join_request_decision(
            to_email=requester.email,
            requested_role=join_request.requested_role.value,
            approved=grant,
            approver_username=approver.username,
            approver_role=approver.role.value if approver.role else "",
            processed_reason=join_request.processed_reason,
            processed_at=join_request.processed_at,
        )
        return StatusResponse(message="Success!")

    async def get_users_login_history(
        self,
        user: GetCurrentUser,
        session: DBSession,
    ) -> list[LoginHistoryResponse]:

        history: list[LoginHistoryResponse] = []
    
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admins only"
            )

        records = await session.scalars(
            select(LoginHistory)
            .options(selectinload(LoginHistory.user))
            .order_by(LoginHistory.signed_in_at.desc())
        )
        login_history = records.all()

        for record in login_history:
            history.append(
                LoginHistoryResponse(
                    username=record.user.username,
                    ip=record.ip,
                    role=record.user.role,
                    logged_in_at=record.signed_in_at,
                )
            )

        return history

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

        if user is None or not AuthProvider.check_password(
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

        login_history_record = LoginHistory(
            user_id=user.id,
            ip=address,
        )

        session.add(login_history_record)
        await session.commit()

        max_age = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
        access_token = JWTProvider.create_access_token(user.id)

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,  # True in production with HTTPS
            samesite="lax",
            max_age=max_age,
            expires=max_age,
            path="/",
        )

        return {"message": "Login successful"}

    async def get_me(self, user: GetCurrentUser) -> UserResponse:

        return UserResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            role=user.role,
            email=user.email,
        )

    async def logout(self, response: Response):
        response.delete_cookie(
            key="access_token",
            path="/",
            httponly=True,
            secure=True,  # Match your cookie configuration
            samesite="lax",
        )

        return StatusResponse(message="Successfully logged out.")
