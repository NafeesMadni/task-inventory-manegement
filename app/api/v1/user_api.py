import re
from datetime import UTC, datetime
from typing import Annotated

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from redis_fastapi import RateLimitBackendDep
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.types import (
    ActiveApprovalsResponse,
    AuthResponse,
    CreateJoinReqRequest,
    JoinRequestsResponse,
    LoginHistoryResponse,
    LoginRequest,
    OTPVerifyRequest,
    Setup2FAResponse,
    SignupRequest,
    StatusResponse,
    UpdatePassword,
    UserPartialUpdate,
    UserRef,
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
from app.dependencies import DBSession, GetCurrentUser, VerifyTurnstile
from app.services import AuthProvider, EmailManager, JWTProvider, TwoFAProvider
from app.services.auth_manager import TokenPurpose


class UserAPI:
    def __init__(self) -> None:
        self.settings = get_settings()

        self.router = APIRouter(prefix="/user", tags=["User Endpoint"])

        self._register_routes()

        oauth = OAuth()

        oauth.register(
            name="google",
            client_id=self.settings.GOOGLE_CLIENT_ID,
            client_secret=self.settings.GOOGLE_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

        self.google_oauth = oauth.google

        self.email_manager = EmailManager()
        self.twofa_provider = TwoFAProvider()

    def _register_routes(self) -> None:
        # Simple Signup/Login flow
        self.router.add_api_route(
            "/signup",
            endpoint=self.signup,
            methods=["POST"],
            response_model=AuthResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/login",
            endpoint=self.login,
            methods=["POST"],
            response_model=AuthResponse,
            status_code=status.HTTP_200_OK,
        )

        # OAuth2 Login Endpoints
        self.router.add_api_route(
            "/google-login",
            endpoint=self.google_login,
            methods=["GET"],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/auth/callback",
            endpoint=self.auth_callback,
            name="auth_callback",
            methods=["GET"],
            status_code=status.HTTP_200_OK,
        )

        # 2FA Setup and Activate
        self.router.add_api_route(
            "/2fa/setup",
            endpoint=self.setup_2fa,
            methods=["PATCH"],
            response_model=Setup2FAResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/2fa/activate",
            endpoint=self.activate_2fa,
            methods=["PATCH"],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/2fa/verify",
            endpoint=self.verify_2fa,
            methods=["POST"],
            response_model=StatusResponse,
            status_code=status.HTTP_200_OK,
        )

        # Update user info
        self.router.add_api_route(
            "",
            endpoint=self.update_user_info,
            methods=["PATCH"],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/password",
            endpoint=self.update_password,
            methods=["PATCH"],
            response_model=StatusResponse,
            status_code=status.HTTP_200_OK,
        )

        # Get user info
        self.router.add_api_route(
            "/me",
            endpoint=self.get_me,
            methods=["GET"],
            response_model=UserResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/active-users",
            endpoint=self.get_active_users,
            methods=["GET"],
            response_model=list[UserRef],
            status_code=status.HTTP_200_OK,
        )

        # JoinRequest flow
        self.router.add_api_route(
            "/active-approvals",
            endpoint=self.get_active_approvals,
            methods=["GET"],
            response_model=list[ActiveApprovalsResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/create-join-requests",
            endpoint=self.create_join_request,
            methods=["POST"],
            response_model=StatusResponse,
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

        # Track user login activity
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

    @staticmethod
    async def set_access_token(
        user_id: int, request: Request, response: Response, session: DBSession
    ) -> None:

        exp_minutes = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES
        max_age = exp_minutes * 60

        access_token, session_id = JWTProvider.create_token(
            user_id, TokenPurpose.ACCESS, exp_minutes
        )

        login_history = LoginHistory(
            user_id=user_id,
            session_id=session_id,
            ip=request.client.host if request.client else "",
        )

        session.add(login_history)
        await session.commit()

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

    @staticmethod
    async def set_2fa_token(user_id: int, response: Response) -> None:
        exp_minutes = 5
        max_age = exp_minutes * 60

        pre_auth_token, _ = JWTProvider.create_token(
            user_id, TokenPurpose.TWO_FA_VERIFICATION, exp_minutes
        )

        response.set_cookie(
            key="pre_auth_token",
            value=pre_auth_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=max_age,
            path="/api/v1/user/2fa/verify",
        )

    @staticmethod
    async def delete_access_token(
        user_id: int, request: Request, response: Response, session: DBSession
    ) -> None:

        token = request.cookies.get("access_token")

        if token:
            payload = JWTProvider.decode_token(token)
            session_id = payload["jti"]

            login_history = await session.scalar(
                select(LoginHistory).where(
                    LoginHistory.user_id == user_id,
                    LoginHistory.session_id == session_id,
                    LoginHistory.signed_out_at.is_(None),
                )
            )

            if login_history:
                login_history.signed_out_at = datetime.now(UTC)
                await session.commit()

        # Remove the cookie anyway login_history exists or not
        response.delete_cookie(
            key="access_token",
            path="/",
            httponly=True,
            secure=True,
            samesite="lax",
        )

    async def signup(
        self,
        _: VerifyTurnstile,
        request: Request,
        payload: SignupRequest,
        session: DBSession,
        response: Response,
    ) -> AuthResponse:
        """Responsible for handling passsword-based user signups"""
        existing_user = await session.scalar(
            select(User).where(
                or_(User.email == payload.email, User.username == payload.username)
            )
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email or username already exists.",
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
        await session.commit()

        await self.set_access_token(user.id, request, response, session)

        return AuthResponse(
            redirect_url="/create-join-request",
            message="You're successfully signed-up, please submit a join request to get access to the system.",
        )

    async def login(
        self,
        _: VerifyTurnstile,
        payload: LoginRequest,
        request: Request,
        response: Response,
        session: DBSession,
        limiter: RateLimitBackendDep,
    ) -> AuthResponse:
        """Simple Login Flow"""

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
            .options(selectinload(User.join_request))
            .where(User.email == str(payload.email))
        )

        if (
            user is None
            or not user.hashed_password  # this account probably link to google, so only /google-login work for this...
            or not AuthProvider.check_password(payload.password, user.hashed_password)
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

        message = "Login successful"

        join_req = user.join_request

        redirect_url: str | None = None

        if not join_req:
            redirect_url = "/create-join-request"
            message = "You're logged in, please submit a join request to get access to the system."

        elif join_req.status == JoinRequestStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your access request has been rejected",
            )

        elif not user.role or join_req.status == JoinRequestStatus.PENDING:
            response.status_code = status.HTTP_403_FORBIDDEN
            message = "You're logged in, please wait for access approval."

        session.add(user)
        await session.flush()
        await session.commit()

        if user.is_2fa_enabled:
            await self.set_2fa_token(user.id, response)

            # set access cookies on successful 2FA verification
            return AuthResponse(message="2FA required!", redirect_url="/2fa/verify")

        await self.set_access_token(user.id, request, response, session)

        return AuthResponse(message=message, redirect_url=redirect_url)

    async def google_login(self, request: Request):
        """
        Initiate Google OAuth 2.0 authentication.

        Generates the Google OAuth authorization URL and redirects the user
        to Google's consent screen. After successful authentication, Google
        redirects the user to the registered auth_callback endpoint.
        """

        redirect_uri = request.url_for("auth_callback")
        return await self.google_oauth.authorize_redirect(request, redirect_uri)

    async def _generate_username(self, session: DBSession, email: str) -> str:
        base = (
            re.sub(r"[^a-z0-9_]", "", email.split("@")[0].lower())[:90] or "user"
        )  # keep only first 90 letters
        candidate, n = base, 0
        while await session.scalar(select(User.id).where(User.username == candidate)):
            n += 1
            candidate = f"{base}{n}"  # update accordingly if already exists
        return candidate

    async def auth_callback(
        self, request: Request, session: DBSession
    ) -> RedirectResponse:
        """Handler for Google SignUp/SignIn"""

        def to(path: str) -> RedirectResponse:
            return RedirectResponse(url=path, status_code=status.HTTP_303_SEE_OTHER)

        try:
            token = await self.google_oauth.authorize_access_token(request)
        except OAuthError:
            return to("/signin?error=google_failed")

        user_info = await self.google_oauth.userinfo(token=token)

        if not user_info.get("email_verified"):
            return to("/signin?error=google_unverified")

        email = user_info["email"]

        existing_user = await session.scalar(
            select(User)
            .options(selectinload(User.join_request))
            .where(User.email == email)
        )

        if existing_user:
            if existing_user.google_id and existing_user.google_id != user_info["sub"]:
                return to("/signin?error=google_failed")

            join_req = existing_user.join_request
            if join_req and join_req.status == JoinRequestStatus.REJECTED:
                return to("/signin?error=access_rejected")

            existing_user.google_id = user_info["sub"]
            user = existing_user
        else:
            # First-time Google signup: account only, the role is requested afterwards.
            user = User(
                google_id=user_info["sub"],
                first_name=user_info.get("given_name", ""),
                last_name=user_info.get("family_name", ""),
                username=await self._generate_username(session, email),
                email=email,
            )
            session.add(user)
            await session.flush()

        await session.commit()

        if not user.role:
            target = "/create-join-request"
        elif user.role == UserRole.DEVELOPER:
            target = "/devices"
        else:
            target = "/dashboard"

        redirect = to("/2fa/verify") if user.is_2fa_enabled else to(target)

        if user.is_2fa_enabled:
            await self.set_2fa_token(user.id, redirect)
        else:
            await self.set_access_token(user.id, request, redirect, session)
        return redirect

    async def setup_2fa(
        self, user: GetCurrentUser, session: DBSession
    ) -> Setup2FAResponse:

        if user.is_2fa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is already enabled!",
            )

        secret = self.twofa_provider.generate_secret()
        user.totp_secret = self.twofa_provider.encrypt_2fa_secret(secret)
        uri = self.twofa_provider.get_provisioning_uri(
            secret=secret, user_email=user.email, issuer_name=self.settings.APP_NAME
        )

        await session.commit()

        return Setup2FAResponse(uri=uri)

    async def activate_2fa(
        self, payload: OTPVerifyRequest, user: GetCurrentUser, session: DBSession
    ):
        if user.is_2fa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is already enabled!",
            )

        if not user.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please Setup two-factor authentication!",
            )

        secret = self.twofa_provider.decrypt_2fa_secret(user.totp_secret)
        is_valid = self.twofa_provider.verify_totp_code(
            secret=secret, code=payload.code
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid code!"
            )

        user.is_2fa_enabled = True
        await session.commit()

    async def verify_2fa(
        self,
        payload: OTPVerifyRequest,
        request: Request,
        session: DBSession,
        response: Response,
    ):
        token = request.cookies.get("pre_auth_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired, please login again.",
            )

        jwt_payload = JWTProvider.decode_token(token)

        try:
            user_id = int(jwt_payload["sub"])

            if jwt_payload["purpose"] != TokenPurpose.TWO_FA_VERIFICATION:
                raise TypeError

        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2fa verification token.",
            )

        user = await session.scalar(
            select(User).where(User.id == user_id, User.email == payload.email)
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User not found!"
            )

        if not user.is_2fa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled.",
            )

        if not user.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please Setup two-factor authentication!",
            )

        secret = self.twofa_provider.decrypt_2fa_secret(user.totp_secret)
        is_valid = self.twofa_provider.verify_totp_code(
            secret=secret, code=payload.code
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid code!"
            )

        # Set access token on success
        await self.set_access_token(user.id, request, response, session)

        response.delete_cookie(
            key="pre_auth_token",
            path="/api/v1/user/2fa/verify",
            httponly=True,
            secure=True,
            samesite="lax",
        )

        return StatusResponse(message="Two-factor authentication verified.")

    async def update_user_info(
        self, payload: UserPartialUpdate, user: GetCurrentUser, session: DBSession
    ):
        if await session.scalar(select(User).where(User.username == payload.username)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists.",
            )

        user = await session.get(User, user.id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found!"
            )

        update_data = payload.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        await session.commit()

    async def update_password(
        self, payload: UpdatePassword, user: GetCurrentUser, session: DBSession
    ) -> StatusResponse:
        if payload.new_password == payload.old_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both passwords are same, please use different password!",
            )

        if user.hashed_password and AuthProvider.check_password(
            payload.old_password, user.hashed_password
        ):
            user.hashed_password = AuthProvider.get_hashed_password(
                payload.new_password
            )
            await session.commit()
            return StatusResponse(message="Password updated successfully.")

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid password!"
        )

    async def get_me(self, user: GetCurrentUser) -> UserResponse:

        return UserResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            role=user.role,
            email=user.email,
            is_2fa_enabled=user.is_2fa_enabled,
        )

    async def get_active_users(
        self, user: GetCurrentUser, session: DBSession
    ) -> list[UserRef]:

        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin only!"
            )
        results = await session.scalars(select(User).where(User.role.is_not(None)))
        active_users = results.all()

        return [
            UserRef(
                id=u.id,
                username=u.username,
                role=u.role,
                email=u.email,
            )
            for u in sorted(
                active_users, key=lambda user: user.created_at, reverse=True
            )
        ]

    async def get_active_approvals(
        self, _: GetCurrentUser, session: DBSession
    ) -> list[ActiveApprovalsResponse]:

        result = await session.execute(
            select(User.id, User.username, User.role).where(
                User.role != UserRole.DEVELOPER
            )
        )
        approvals = result.all()
        return [
            ActiveApprovalsResponse(
                id=approval.id, username=approval.username, role=approval.role
            )
            for approval in approvals
        ]

    async def create_join_request(
        self,
        payload: CreateJoinReqRequest,
        user: GetCurrentUser,
        session: DBSession,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> StatusResponse:
        if payload.requested_role == UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin role cannot be requested.",
            )

        if user.role:
            response.status_code = status.HTTP_409_CONFLICT
            return StatusResponse(message="You already have an assigned role.")

        # Prevent duplicate join requests
        existing_join_request = await session.scalar(
            select(JoinRequest).where(JoinRequest.requested_by == user.id)
        )

        if existing_join_request:
            if existing_join_request.status == JoinRequestStatus.REJECTED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your access request has been rejected",
                )

            if existing_join_request.status == JoinRequestStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You already have a join request submitted.",
                )

        if payload.requested_role == UserRole.DEVELOPER:
            required_role = UserRole.SUPERVISOR
            approver_name = "supervisor"

        elif payload.requested_role == UserRole.SUPERVISOR:
            required_role = UserRole.ADMIN
            approver_name = "admin"

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role requested.",
            )

        requested_from_user = await session.scalar(
            select(User).where(
                User.id == payload.requested_from,
                User.role == required_role,
            )
        )

        if not requested_from_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The selected {approver_name} was not found or is not eligible to receive this request.",
            )

        join_request = JoinRequest(
            requested_role=payload.requested_role,
            requested_by=user.id,
            requested_from=requested_from_user.id,
            request_note=payload.request_note,
        )

        session.add(join_request)
        await session.commit()
        await session.refresh(join_request)

        background_tasks.add_task(
            self.email_manager.send_join_request_notification,
            to_email=requested_from_user.email,
            approver_username=requested_from_user.username,
            requester_username=user.username,
            requester_name=f"{user.first_name} {user.last_name}",
            requester_email=user.email,
            requested_role=join_request.requested_role.value,
            requested_at=join_request.created_at,
        )

        return StatusResponse(
            message=(
                "Your join request has been submitted successfully. You will be notified once it has been reviewed."
            )
        )

    async def get_join_requests(
        self, user: GetCurrentUser, session: DBSession, response: Response
    ) -> list[JoinRequestsResponse]:

        stmt = select(JoinRequest).options(
            selectinload(JoinRequest.requester),
            selectinload(JoinRequest.requested_from_user),
            selectinload(JoinRequest.processor),
        )

        if user.role == UserRole.ADMIN:
            # Admin can see all join requests
            pass

        elif user.role == UserRole.SUPERVISOR:
            # Supervisor can see requests addressed to them
            stmt = stmt.where(JoinRequest.requested_from == user.id)

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You're not authorized to view join requests",
            )

        result = await session.scalars(stmt)
        join_requests = result.all()

        return [
            JoinRequestsResponse(
                id=jr.id,
                requester_role=jr.requested_role,
                requester_username=jr.requester.username,
                approval_role=jr.requested_from_user.role,  # type: ignore
                approval_username=jr.requested_from_user.username,
                request_note=jr.request_note or None,
                status=jr.status,
                requested_at=jr.created_at,
                processed_by_username=jr.processor.username if jr.processor else None,
                processed_by_role=jr.processor.role if jr.processor else None,
                processed_at=jr.processed_at or None,
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
        background_tasks: BackgroundTasks,
        reason: Annotated[str | None, Query()] = None,
    ) -> StatusResponse:

        if user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized."
            )

        # ? Can admin process any request?

        join_request = await session.scalar(
            select(JoinRequest)
            .options(
                selectinload(JoinRequest.requester),
                selectinload(JoinRequest.requested_from_user),
            )
            .where(
                JoinRequest.id == join_request_id,
                JoinRequest.requested_from == user.id,
            )
        )

        if not join_request:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(
                message="Request might not be found or you are not authorized to manage this request.",
            )

        if join_request.requested_role == UserRole.ADMIN:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(message="Invalid requested role.")

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
        background_tasks.add_task(
            self.email_manager.send_join_request_decision,
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
        self, user: GetCurrentUser, session: DBSession
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
                    logged_out_at=record.signed_out_at,
                )
            )

        return history

    async def logout(
        self,
        user: GetCurrentUser,
        request: Request,
        response: Response,
        session: DBSession,
    ) -> StatusResponse:

        await self.delete_access_token(user.id, request, response, session)

        return StatusResponse(message="Successfully logged out.")
