from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_check_constraint, enum_column
from app.database.models.enums import AssignmentReturnType, DeviceCondition

if TYPE_CHECKING:
    from app.database.models import Device, DevicesRequest, User


class DeviceAssignment(Base):
    __tablename__ = "device_assignments"

    __table_args__ = (
        # Search all assignments by device_id
        Index(
            "ix_device_assignments_device_id",
            "device_id",
        ),
        # Partial Unique Index: device can have multiple assignment records, but only one active assignment at a time
        Index(
            "uq_device_active_assignment",
            "device_id",
            unique=True,
            postgresql_where=text("returned_at IS NULL"),
        ),
        # A request can generate only one assignment
        UniqueConstraint("request_id", name="uq_device_assignment_request"),
        # an assignment is ended exactly when it has a return type
        CheckConstraint(
            "(returned_at IS NULL) = (return_type IS NULL)",
            name="ck_device_assignments_return_consistent",
        ),
        enum_check_constraint(
            AssignmentReturnType, "return_type", "ck_device_assignments_return_type"
        ),
        enum_check_constraint(
            DeviceCondition,
            "condition_on_issue",
            "ck_device_assignments_condition_on_issue",
        ),
        enum_check_constraint(
            DeviceCondition,
            "condition_on_return",
            "ck_device_assignments_condition_on_return",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False
    )

    # Might be directly assigned by Admin or other higher authority, so for that reason, no request might be made for a device
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices_requests.id", ondelete="SET NULL"), nullable=True
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

    returned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    return_type: Mapped[AssignmentReturnType | None] = mapped_column(
        enum_column(AssignmentReturnType, "assignment_return_type"), nullable=True
    )

    return_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    condition_on_issue: Mapped[DeviceCondition | None] = mapped_column(
        enum_column(DeviceCondition, "device_condition_issue"), nullable=True
    )

    condition_on_return: Mapped[DeviceCondition | None] = mapped_column(
        enum_column(DeviceCondition, "device_condition_return"), nullable=True
    )

    # Relationship
    device: Mapped[Device] = relationship(back_populates="assignments")

    assigned_to_user: Mapped[User] = relationship(
        back_populates="device_assignments", foreign_keys=[assigned_to]
    )

    assigned_by_user: Mapped[User | None] = relationship(
        back_populates="device_assignments_assigned_by", foreign_keys=[assigned_by]
    )

    returned_by_user: Mapped[User | None] = relationship(foreign_keys=[returned_by])

    request: Mapped[DevicesRequest | None] = relationship(
        back_populates="assignment", foreign_keys=[request_id]
    )
