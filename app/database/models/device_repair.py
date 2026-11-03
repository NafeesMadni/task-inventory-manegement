from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_column
from app.database.models.enums import RepairStatus

if TYPE_CHECKING:
    from app.database.models import Device, NewRepairDevicesRequest


class DeviceRepair(Base):
    __tablename__ = "device_repairs"

    __table_args__ = (
        Index(
            "uq_device_repairs_one_active_per_device",
            "device_id",
            unique=True,
            postgresql_where=text("status IN ('scheduled', 'in_progress')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False
    )

    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    request_id: Mapped[int] = mapped_column(
        ForeignKey("new_repair_devices_requests.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )

    note: Mapped[str] = mapped_column(Text, nullable=False)

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    status: Mapped[RepairStatus] = mapped_column(
        enum_column(RepairStatus, "repair_status"),
        default=RepairStatus.SCHEDULED,
        nullable=False,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships

    # A device repair is associated with a specific device, and a device can have multiple repairs over time.
    device: Mapped[Device] = relationship(
        back_populates="repairs", foreign_keys=[device_id]
    )  # Many-to-one

    # A device repair is associated with a specific repair request, and a repair request can have only one repair.
    request: Mapped[NewRepairDevicesRequest] = relationship(
        back_populates="repair", foreign_keys=[request_id]
    )  # One-to-one
