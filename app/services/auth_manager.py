from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

import bcrypt
import jwt
import pyotp
from cryptography.fernet import Fernet
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


class TokenPurpose(StrEnum):
    ACCESS = "access"
    TWO_FA_VERIFICATION = "2fa_verification"


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
    def create_token(
        user_id: int, purpose: TokenPurpose, exp_minutes: int
    ) -> tuple[str, str]:
        session_id = str(uuid4())
        expires_at = datetime.now(UTC) + timedelta(minutes=exp_minutes)

        payload = {
            "sub": str(user_id),
            "jti": session_id,
            "purpose": purpose,
            "exp": expires_at,
        }

        return jwt.encode(
            payload=payload,
            key=settings.JWT_SECRET_KEY,
            algorithm=settings.ALGORITHM,
        ), session_id

    @staticmethod
    def decode_token(token: str) -> dict:
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


class TwoFAProvider:
    def __init__(self):
        self.fernet = Fernet(settings.TWO_FACTOR_ENCRYPTION_KEY.encode())

    def generate_secret(self) -> str:
        """Generates a random 32-character base32 secret key."""
        return pyotp.random_base32()

    def get_provisioning_uri(
        self, secret: str, user_email: str, issuer_name: str
    ) -> str:
        """Generates the otpauth:// URI used by QR code generators and authenticator apps."""
        totp = pyotp.TOTP(secret)  # type: ignore
        return totp.provisioning_uri(name=user_email, issuer_name=issuer_name)

    def encrypt_2fa_secret(self, secret: str) -> str:
        return self.fernet.encrypt(secret.encode()).decode()

    def decrypt_2fa_secret(self, encrypted_secret: str) -> str:
        return self.fernet.decrypt(encrypted_secret.encode()).decode()

    def verify_totp_code(self, secret: str, code: str) -> bool:
        """Verifies a 6-digit TOTP code against the user's secret."""
        totp = pyotp.TOTP(secret)  # type: ignore

        # planing to set valid_window=1 allows a 30-second buffer before/after for minor clock drift
        return totp.verify(code)
