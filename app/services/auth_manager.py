from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


class AuthProvider:
    @staticmethod
    def get_hashed_password(plain_text_password: str) -> str:
        plain_password_bytes = plain_text_password.encode("utf-8")

        hashed_password = bcrypt.hashpw(
            plain_password_bytes,
            bcrypt.gensalt(14),
        )

        return hashed_password.decode("utf-8")

    @staticmethod
    def check_password(plain_text_password: str, hashed_password: str) -> bool:
        plain_password_bytes = plain_text_password.encode("utf-8")
        hashed_password_bytes = hashed_password.encode("utf-8")

        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)


class JWTProvider:
    @staticmethod
    def create_access_token(user_id: int) -> tuple[str, str]:
        session_id = str(uuid4())
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        payload = {
            "sub": str(user_id),
            "jti": session_id,
            "exp": expires_at,
        }

        return jwt.encode(
            payload=payload,
            key=settings.JWT_SECRET_KEY,
            algorithm=settings.ALGORITHM,
        ), session_id

    @staticmethod
    def decode_access_token(token: str) -> dict:
        try:
            return jwt.decode(
                jwt=token,
                key=settings.JWT_SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
