from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_column
from app.database.models.enums import DeviceCondition

if TYPE_CHECKING:
    from app.database.models import Device, NewRepairDevicesRequest, User


class DeviceAssignment(Base):
    __tablename__ = "device_assignments"

    __table_args__ = (
        # A device can have only one active assignment
        Index(
            "uq_device_active_assignment",
            "device_id",
            unique=True,
            postgresql_where=text("returned_at IS NULL"),
        ),
        # A request can generate only one assignment
        UniqueConstraint("request_id", name="uq_device_assignment_request"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False
    )

    # Might be directly assigned by Admin or other higher authority, so for that reason, no request might be made for a device
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("new_repair_devices_requests.id", ondelete="SET NULL"), nullable=True
    )

    assigned_to: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Useful for tracking direct admin assignments.
    assigned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    condition_on_issue: Mapped[DeviceCondition | None] = mapped_column(
        enum_column(DeviceCondition, "device_condition_issue"), nullable=True
    )

    condition_on_return: Mapped[DeviceCondition | None] = mapped_column(
        enum_column(DeviceCondition, "device_condition_return"), nullable=True
    )

    device: Mapped[Device] = relationship(back_populates="assignments")

    # Relationship

    assigned_to_user: Mapped[User] = relationship(
        back_populates="device_assignments", foreign_keys=[assigned_to]
    )

    assigned_by_user: Mapped[User | None] = relationship(
        back_populates="device_assignments_assigned_by", foreign_keys=[assigned_by]
    )

    request: Mapped[NewRepairDevicesRequest | None] = relationship(
        back_populates="assignment", foreign_keys=[request_id]
    )
