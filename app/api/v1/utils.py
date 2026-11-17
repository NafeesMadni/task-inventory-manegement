from datetime import UTC, datetime

from app.api.v1.types import DeviceRef, UserRef
from app.database.models import Device, User


def user_ref(u: User | None) -> UserRef | None:
    return (
        UserRef(id=u.id, username=u.username, role=u.role, email=u.email) if u else None
    )


def device_ref(d: Device | None) -> DeviceRef | None:
    return (
        DeviceRef(
            id=d.id,
            name=d.name,
            ram_gb=d.ram_gb,
            hdd_gb=d.hdd_gb,
            ssd_gb=d.ssd_gb,
            processor=d.processor,
            brand=d.brand,
            status=d.status,
            condition=d.condition,
            created_at=d.created_at,
        )
        if d
        else None
    )


def to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC)
