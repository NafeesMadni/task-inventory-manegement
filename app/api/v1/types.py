from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.database.models import JoinRequestStatus, UserRole


class SignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    first_name: str = Field(min_length=3, max_length=100)
    last_name: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8)
    requested_role: UserRole = Field(default=UserRole.DEVELOPER)
    requested_from: int | None = Field(
        default=None
    )  # only for developer role, this is the supervisor id
    request_note: str | None = Field(default=None)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr


class SupervisorResponse(BaseModel):
    id: int
    username: str


class JoinRequestsResponse(BaseModel):
    id: int
    requested_role: UserRole
    requested_by: int
    requested_from: int
    request_note: str | None
    status: JoinRequestStatus

    requested_at: datetime

    processed_by: int | None
    processed_at: datetime | None
    processed_reason: str | None
