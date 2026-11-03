from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_check_constraint, enum_column
from app.database.models.enums import JoinRequestStatus, UserRole

if TYPE_CHECKING:
    from app.database.models import User


class JoinRequest(Base):
    __tablename__ = "join_requests"

    __table_args__ = (
        enum_check_constraint(
            UserRole,
            "requested_role",
            "ck_join_requests_requested_role",
        ),
        enum_check_constraint(
            JoinRequestStatus,
            "status",
            "ck_join_requests_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    requested_role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "requested_user_role"), nullable=False
    )

    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    requested_from: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    request_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[JoinRequestStatus] = mapped_column(
        enum_column(JoinRequestStatus, "join_request_status"),
        default=JoinRequestStatus.PENDING,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships

    # The user who made the join request
    requester: Mapped[User] = relationship(
        back_populates="join_requests", foreign_keys=[requested_by]
    )

    # The user who received the join request (supervisor/admin)
    requested_from_user: Mapped[User] = relationship(
        back_populates="received_join_requests", foreign_keys=[requested_from]
    )
