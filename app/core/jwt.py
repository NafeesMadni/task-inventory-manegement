from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings


class JWTProvider:
    @staticmethod
    def create_access_token(user_id: int) -> str:
        expires_at = datetime.now(UTC) + timedelta(
            minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES
        )

        payload = {
            "sub": str(user_id),
            "exp": expires_at,
        }

        return jwt.encode(
            payload=payload,
            key=get_settings().JWT_SECRET_KEY,
            algorithm=get_settings().ALGORITHM,
        )

    @staticmethod
    def decode_access_token(token: str) -> dict:
        try:
            decoded = jwt.decode(
                jwt=token,
                key=get_settings().JWT_SECRET_KEY,
                algorithms=[get_settings().ALGORITHM],
            )
            return decoded
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
