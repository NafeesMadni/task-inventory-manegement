from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.models import Device, DeviceStatus, User, UserRole
from app.services.auth_manager import AuthProvider

settings = get_settings()


async def create_initial_admin(session: AsyncSession) -> None:
    """This function adds admin and demo devices on startup"""

    admin = await session.scalar(select(User).where(User.role == UserRole.ADMIN))

    if admin:
        return

    existing_user = await session.scalar(
        select(User).where(User.email == settings.INITIAL_ADMIN_EMAIL)
    )

    if existing_user:
        raise RuntimeError("Initial admin email already belongs to a non-admin user.")

    admin = User(
        username="admin",
        first_name="Nafees",
        last_name="Madni",
        email=settings.INITIAL_ADMIN_EMAIL,
        hashed_password=AuthProvider.get_hashed_password(
            settings.INITIAL_ADMIN_PASSWORD
        ),
        role=UserRole.ADMIN,
    )

    session.add(admin)

    demo_devices = [
        Device(
            name="Dell Latitude 5420",
            serial_no="DELL-LAT-2024-001",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core i5-1145G7",
            brand="Dell",
            purchase_date=datetime(2024, 3, 15, tzinfo=UTC),
            purchase_price=145000.00,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="HP EliteBook 840 G8",
            serial_no="HP-ELT-2024-002",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core i7-1165G7",
            brand="HP",
            purchase_date=datetime(2024, 5, 20, tzinfo=UTC),
            purchase_price=175000.00,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="Lenovo ThinkPad T14",
            serial_no="LEN-TPD-2024-003",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="AMD Ryzen 7 PRO 5850U",
            brand="Lenovo",
            purchase_date=datetime(2024, 7, 10, tzinfo=UTC),
            purchase_price=210000.00,
            status=DeviceStatus.ASSIGNED,
        ),
        Device(
            name="Dell Latitude 5520",
            serial_no="DELL-LAT-2023-004",
            ram_gb=8,
            ssd_gb=256,
            hdd_gb=0,
            processor="Intel Core i5-1135G7",
            brand="Dell",
            purchase_date=datetime(2023, 8, 12, tzinfo=UTC),
            purchase_price=115000.00,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="HP ProBook 450 G9",
            serial_no="HP-PRO-2024-005",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=1000,
            processor="Intel Core i5-1235U",
            brand="HP",
            purchase_date=datetime(2024, 9, 5, tzinfo=UTC),
            purchase_price=155000.00,
            status=DeviceStatus.ASSIGNED,
        ),
    ]

    session.add_all(demo_devices)
    await session.commit()
