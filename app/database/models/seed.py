from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.models import Device, DeviceCondition, DeviceStatus, User, UserRole
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
        username="admin-user",
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
        # Apple MacBooks
        Device(
            name="MacBook Pro 16-inch M3 Pro",
            serial_no="APL-MBP-2024-001",
            ram_gb=18,
            ssd_gb=512,
            hdd_gb=0,
            processor="Apple M3 Pro",
            brand="Apple",
            purchase_date=datetime(2024, 2, 15, tzinfo=UTC),
            purchase_price=650000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="MacBook Air 15-inch M2",
            serial_no="APL-MBA-2023-002",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Apple M2",
            brand="Apple",
            purchase_date=datetime(2023, 9, 10, tzinfo=UTC),
            purchase_price=420000.00,
            condition=DeviceCondition.GOOD,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="MacBook Pro 14-inch M3 Max",
            serial_no="APL-MBP-2024-003",
            ram_gb=36,
            ssd_gb=1024,
            hdd_gb=0,
            processor="Apple M3 Max",
            brand="Apple",
            purchase_date=datetime(2024, 4, 20, tzinfo=UTC),
            purchase_price=950000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="MacBook Air 13-inch M1",
            serial_no="APL-MBA-2022-004",
            ram_gb=8,
            ssd_gb=256,
            hdd_gb=0,
            processor="Apple M1",
            brand="Apple",
            purchase_date=datetime(2022, 6, 12, tzinfo=UTC),
            purchase_price=220000.00,
            condition=DeviceCondition.FAIR,
            status=DeviceStatus.AVAILABLE,
        ),
        # Dell Laptops
        Device(
            name="Dell XPS 15 9530",
            serial_no="DELL-XPS-2024-005",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="Intel Core i7-13700H",
            brand="Dell",
            purchase_date=datetime(2024, 3, 15, tzinfo=UTC),
            purchase_price=480000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="Dell Latitude 5420",
            serial_no="DELL-LAT-2024-006",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core i5-1145G7",
            brand="Dell",
            purchase_date=datetime(2024, 3, 15, tzinfo=UTC),
            purchase_price=145000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="Dell Latitude 7440",
            serial_no="DELL-LAT-2024-007",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core i7-1365U",
            brand="Dell",
            purchase_date=datetime(2024, 5, 10, tzinfo=UTC),
            purchase_price=350000.00,
            condition=DeviceCondition.GOOD,
            status=DeviceStatus.AVAILABLE,
        ),
        # HP Laptops
        Device(
            name="HP EliteBook 840 G8",
            serial_no="HP-ELT-2024-008",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core i7-1165G7",
            brand="HP",
            purchase_date=datetime(2024, 5, 20, tzinfo=UTC),
            purchase_price=175000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="HP EliteBook 840 G10",
            serial_no="HP-ELT-2024-009",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="Intel Core i7-1355U",
            brand="HP",
            purchase_date=datetime(2024, 8, 15, tzinfo=UTC),
            purchase_price=380000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="HP ZBook Firefly 16 G10",
            serial_no="HP-ZBK-2024-010",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="Intel Core i7-1365U",
            brand="HP",
            purchase_date=datetime(2024, 9, 5, tzinfo=UTC),
            purchase_price=450000.00,
            condition=DeviceCondition.GOOD,
            status=DeviceStatus.AVAILABLE,
        ),
        # Lenovo Laptops
        Device(
            name="Lenovo ThinkPad T14 Gen 3",
            serial_no="LEN-TPD-2024-011",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="AMD Ryzen 7 PRO 6850U",
            brand="Lenovo",
            purchase_date=datetime(2024, 7, 10, tzinfo=UTC),
            purchase_price=320000.00,
            condition=DeviceCondition.GOOD,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="Lenovo ThinkPad X1 Carbon Gen 11",
            serial_no="LEN-X1C-2024-012",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core i7-1355U",
            brand="Lenovo",
            purchase_date=datetime(2024, 6, 15, tzinfo=UTC),
            purchase_price=410000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="Lenovo Legion 5 Pro",
            serial_no="LEN-LEG-2024-013",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="AMD Ryzen 7 7745HX",
            brand="Lenovo",
            purchase_date=datetime(2024, 10, 1, tzinfo=UTC),
            purchase_price=520000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        # ASUS Laptops
        Device(
            name="ASUS ZenBook 14 OLED",
            serial_no="ASUS-ZBK-2024-014",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core Ultra 7 155H",
            brand="ASUS",
            purchase_date=datetime(2024, 4, 12, tzinfo=UTC),
            purchase_price=340000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="ASUS ROG Zephyrus G14",
            serial_no="ASUS-ROG-2024-015",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="AMD Ryzen 9 8945HS",
            brand="ASUS",
            purchase_date=datetime(2024, 8, 20, tzinfo=UTC),
            purchase_price=550000.00,
            condition=DeviceCondition.GOOD,
            status=DeviceStatus.AVAILABLE,
        ),
        # Microsoft Surface
        Device(
            name="Microsoft Surface Laptop 5",
            serial_no="MS-SUR-2024-016",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core i7-1255U",
            brand="Microsoft",
            purchase_date=datetime(2024, 2, 25, tzinfo=UTC),
            purchase_price=310000.00,
            condition=DeviceCondition.GOOD,
            status=DeviceStatus.AVAILABLE,
        ),
        # Acer Laptops
        Device(
            name="Acer Swift X 14",
            serial_no="ACR-SWX-2024-017",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=0,
            processor="Intel Core Ultra 7 155H",
            brand="Acer",
            purchase_date=datetime(2024, 6, 5, tzinfo=UTC),
            purchase_price=290000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        # MSI Laptops
        Device(
            name="MSI Creator Z16",
            serial_no="MSI-CRZ-2024-018",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="Intel Core i7-12700H",
            brand="MSI",
            purchase_date=datetime(2024, 7, 18, tzinfo=UTC),
            purchase_price=430000.00,
            condition=DeviceCondition.GOOD,
            status=DeviceStatus.AVAILABLE,
        ),
        # Additional Business Laptops
        Device(
            name="Dell Precision 5680",
            serial_no="DELL-PRS-2024-019",
            ram_gb=32,
            ssd_gb=1024,
            hdd_gb=0,
            processor="Intel Core i7-13800H",
            brand="Dell",
            purchase_date=datetime(2024, 9, 12, tzinfo=UTC),
            purchase_price=580000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
        Device(
            name="HP ProBook 450 G9",
            serial_no="HP-PRO-2024-020",
            ram_gb=16,
            ssd_gb=512,
            hdd_gb=1000,
            processor="Intel Core i5-1235U",
            brand="HP",
            purchase_date=datetime(2024, 9, 5, tzinfo=UTC),
            purchase_price=155000.00,
            condition=DeviceCondition.NEW,
            status=DeviceStatus.AVAILABLE,
        ),
    ]

    session.add_all(demo_devices)
    await session.commit()
