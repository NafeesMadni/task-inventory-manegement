import bcrypt
from fastapi import APIRouter, HTTPException, Request, Response, status
from redis_fastapi import RateLimitBackendDep
from sqlalchemy import select

from app.api.v1.types import LoginRequest, SignupRequest, UserResponse
from app.core.config import get_settings
from app.core.jwt import JWTProvider
from app.database.models import User
from app.dependencies import DBSession, GetCurrentUser


class Auth:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/auth", tags=["Authentication Endpoint"])
        self._register_routes()

    def _get_hashed_password(self, plain_text_password: str) -> str:
        plain_password_bytes = plain_text_password.encode("utf-8")

        hashed_password = bcrypt.hashpw(
            plain_password_bytes,
            bcrypt.gensalt(14),
        )

        return hashed_password.decode("utf-8")

    def _check_password(self, plain_text_password: str, hashed_password: str) -> bool:
        plain_password_bytes = plain_text_password.encode("utf-8")
        hashed_password_bytes = hashed_password.encode("utf-8")

        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/signup",
            endpoint=self.signup,
            methods=["POST"],
            response_model=UserResponse,
            status_code=status.HTTP_201_CREATED,
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
        self, payload: SignupRequest, response: Response, session: DBSession
    ) -> UserResponse:
        existing_user = await session.scalar(
            select(User).where(
                (User.email == payload.email) | (User.username == payload.username)
            )
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email or username already registered",
            )

        user = User(
            username=payload.username,
            email=str(payload.email),
            hashed_password=self._get_hashed_password(payload.password),
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        access_token = JWTProvider.create_access_token(user.id)
        max_age = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            max_age=max_age,
            expires=max_age,
        )

        return UserResponse(id=user.id, username=user.username, email=user.email)

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
        limit = await limiter.peek(key, limit=5, window=WINDOW)

        if limit.remaining == 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts, account temporarily locked.",
                headers={"Retry-After": f"{limit.retry_after / 60:.2f} minutes"},
            )

        user = await session.scalar(
            select(User).where(User.email == str(payload.email))
        )

        if not user or not self._check_password(payload.password, user.hashed_password):
            result = await limiter.hit(key, limit=5, window=WINDOW)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"invalid credentials ({result.remaining} left)",
            )

        max_age = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
        access_token = JWTProvider.create_access_token(user.id)
        response.set_cookie(
            key="access_token", value=access_token, max_age=max_age, expires=max_age
        )

        return {"message": "Login successful"}

    async def get_me(self, user: GetCurrentUser) -> UserResponse:

        return UserResponse(id=user.id, username=user.username, email=user.email)
