from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_check_constraint, enum_column
from app.database.models.enums import DeviceCondition, DeviceStatus

if TYPE_CHECKING:
    from app.database.models import (
        DeviceAssignment,
        DeviceRepair,
        DevicesRequest,
    )


class Device(Base):
    __tablename__ = "devices"

    __table_args__ = (
        enum_check_constraint(
            DeviceStatus,
            "status",
            "ck_devices_status",
        ),
        enum_check_constraint(
            DeviceCondition,
            "condition",
            "ck_devices_condition",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    serial_no: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    ram_gb: Mapped[int] = mapped_column(Integer, nullable=False)

    ssd_gb: Mapped[int] = mapped_column(Integer, default=0)

    hdd_gb: Mapped[int] = mapped_column(Integer, default=0)

    processor: Mapped[str] = mapped_column(String(150), nullable=False)

    brand: Mapped[str] = mapped_column(String(100), nullable=False)

    purchase_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    purchase_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    status: Mapped[DeviceStatus] = mapped_column(
        enum_column(DeviceStatus, "device_status"),
        default=DeviceStatus.AVAILABLE,
        nullable=False,
        index=True,
    )

    condition: Mapped[DeviceCondition] = mapped_column(
        enum_column(DeviceCondition, "device_condition"),
        default=DeviceCondition.NEW,
        nullable=False,
    )

    # None?
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships

    # A device can have multiple repairs, but only one active repair at a time.
    repairs: Mapped[list[DeviceRepair]] = relationship(back_populates="device")

    # A device can have multiple assignments, but only one active assignment at a time.
    assignments: Mapped[list[DeviceAssignment]] = relationship(back_populates="device")

    # A device can have multiple repair/available device requests, but only one active request at a time.
    requests: Mapped[list[DevicesRequest]] = relationship(back_populates="device")
