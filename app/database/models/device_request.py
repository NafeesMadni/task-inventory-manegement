from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func, or_, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_check_constraint, enum_column
from app.database.models.enums import DeviceRequestStatus, DeviceRequestType

if TYPE_CHECKING:
    from app.database.models import (
        Device,
        DeviceAssignment,
        DeviceRepair,
        RequestApproval,
        User,
    )


class DevicesRequest(Base):
    __tablename__ = "devices_requests"

    __table_args__ = (
        CheckConstraint(
            or_(
                text("type = 'new' AND device_id IS NULL"),
                text("type IN ('existing', 'repair') AND device_id IS NOT NULL"),
            ),
            name="ck_device_request_type_device",
        ),
        enum_check_constraint(DeviceRequestType, "type", "ck_devices_requests_type"),
        enum_check_constraint(
            DeviceRequestStatus, "status", "ck_devices_requests_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    issue: Mapped[str] = mapped_column(Text, nullable=False)

    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), nullable=True
    )

    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    pending_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    requested_specs: Mapped[str | None] = mapped_column(Text, nullable=True)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    type: Mapped[DeviceRequestType] = mapped_column(
        enum_column(DeviceRequestType, "device_request_type"), nullable=False
    )

    status: Mapped[DeviceRequestStatus] = mapped_column(
        enum_column(DeviceRequestStatus, "device_request_status"),
        default=DeviceRequestStatus.PENDING,
        nullable=False,
    )

    # Relationships

    requester: Mapped[User] = relationship(
        back_populates="device_requests", foreign_keys=[requested_by]
    )

    pending_approver: Mapped[User | None] = relationship(
        back_populates="pending_device_requests", foreign_keys=[pending_by]
    )

    # A device request can be associated with a specific device, and a device can have multiple requests over time.
    device: Mapped[Device | None] = relationship(
        back_populates="requests", foreign_keys=[device_id]
    )  # Optional one-to-one

    # A device request can have one associated repair, and a repair is linked to one device request.
    repair: Mapped[DeviceRepair | None] = relationship(
        back_populates="request", uselist=False
    )  # Optional one-to-one

    # Get all request approvals associated with this device request
    approvals: Mapped[list[RequestApproval]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )

    assignment: Mapped[DeviceAssignment | None] = relationship(
        back_populates="request", uselist=False
    )
