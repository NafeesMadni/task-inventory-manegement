from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models import User


class LoginHistory(Base):
    __tablename__ = "login_history"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    signed_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        back_populates="login_history", foreign_keys=[user_id]
    )  # For the relationship with the User model, allowing access to the user associated with this login history entry.
