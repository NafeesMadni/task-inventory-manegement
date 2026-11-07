from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models import User


class SupervisorDeveloper(Base):
    __tablename__ = "supervisor_developers"

    __table_args__ = (
        CheckConstraint(
            "supervisor_id != developer_id",
            name="ck_supervisor_developer_different_users",
        ),
        UniqueConstraint("developer_id", name="uq_developer_supervisor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    supervisor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    developer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships

    # Get supervisor details
    supervisor: Mapped[User] = relationship(
        back_populates="supervised_developers", foreign_keys=[supervisor_id]
    )

    # Get developer details
    developer: Mapped[User] = relationship(
        back_populates="supervisor_assignment", foreign_keys=[developer_id]
    )
