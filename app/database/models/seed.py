from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.models import User, UserRole
from app.services.auth_manager import AuthProvider

settings = get_settings()


async def create_initial_admin(session: AsyncSession) -> None:
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
    await session.commit()
