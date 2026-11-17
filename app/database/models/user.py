from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from app.database.models import (
    DeviceAssignment,
    DevicesRequest,
    JoinRequest,
    SupervisorDeveloper,
)
from app.database.models.base import Base, enum_check_constraint, enum_column
from app.database.models.enums import UserRole

if TYPE_CHECKING:
    from app.database.models import LoginHistory, RequestApproval


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        Index(
            "uq_users_single_admin",
            "role",
            unique=True,
            postgresql_where=text("role = 'admin'"),
        ),
        enum_check_constraint(
            UserRole,
            "role",
            "ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    role: Mapped[UserRole | None] = mapped_column(
        enum_column(UserRole, "user_role"), nullable=True
    )

    google_id: Mapped[str | None] = mapped_column(
        unique=True, index=True, nullable=True
    )

    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_2fa_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False, nullable=False
    )

    username: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)

    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships

    # Developers managed by this User WHERE `role=supervisor`
    supervised_developers: Mapped[list[SupervisorDeveloper]] = relationship(
        back_populates="supervisor", foreign_keys=[SupervisorDeveloper.supervisor_id]
    )

    # Supervisor assigned to this this User WHERE `role=developer`
    supervisor_assignment: Mapped[SupervisorDeveloper | None] = relationship(
        back_populates="developer",
        uselist=False,
        foreign_keys=[SupervisorDeveloper.developer_id],
    )

    # This User complete login history
    login_history: Mapped[list[LoginHistory]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # New/Repair/Available Devices requests made by this user
    device_requests: Mapped[list[DevicesRequest]] = relationship(
        back_populates="requester", foreign_keys=[DevicesRequest.requested_by]
    )

    # Currently pending New/Repair/Available Devices requests that this user is responsible for approving (Only Admin/Supervisor)
    pending_device_requests: Mapped[list[DevicesRequest]] = relationship(
        back_populates="pending_approver",
        foreign_keys=[DevicesRequest.pending_by],
    )

    # All device assignments assigned to this user
    device_assignments: Mapped[list[DeviceAssignment]] = relationship(
        back_populates="assigned_to_user", foreign_keys=[DeviceAssignment.assigned_to]
    )

    # All device assignments assigned by this user (Only Admin/Supervisor)
    device_assignments_assigned_by: Mapped[list[DeviceAssignment]] = relationship(
        back_populates="assigned_by_user",
        foreign_keys=[DeviceAssignment.assigned_by],
    )

    # All devices request approvals made by this user
    approvals: Mapped[list[RequestApproval]] = relationship(back_populates="approver")

    # Join requests made by this user
    join_request: Mapped[JoinRequest | None] = relationship(
        back_populates="requester",
        foreign_keys=[JoinRequest.requested_by],
        uselist=False,
    )

    # All join requests received by this user; for supervisors/admin only
    received_join_requests: Mapped[list[JoinRequest]] = relationship(
        back_populates="requested_from_user", foreign_keys=[JoinRequest.requested_from]
    )

    # All join requests processed (approved/rejected) by this user
    processed_join_requests: Mapped[list[JoinRequest]] = relationship(
        back_populates="processor",
        foreign_keys=[JoinRequest.processed_by],
    )


def get_user_loading_options(role: UserRole):
    options = []
    if role in (UserRole.ADMIN, UserRole.SUPERVISOR):
        options.extend([
            selectinload(User.supervised_developers),
            selectinload(User.supervisor_assignment),
            selectinload(User.login_history),
            selectinload(User.device_requests),
            selectinload(User.pending_device_requests),
            selectinload(User.device_assignments),
            selectinload(User.device_assignments_assigned_by),
            selectinload(User.approvals),
            selectinload(User.join_request),
            selectinload(User.received_join_requests),
            selectinload(User.processed_join_requests),
        ])

    elif role == UserRole.DEVELOPER:
        options.extend([
            selectinload(User.supervisor_assignment),
            selectinload(User.login_history),
            selectinload(User.device_requests),
            selectinload(User.device_assignments),
            selectinload(User.join_request),
        ])

    return options
