from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_column
from app.database.models.enums import ApprovalDecision

if TYPE_CHECKING:
    from app.database.models import NewRepairDevicesRequest, User


class RequestApproval(Base):
    __tablename__ = "request_approvals"

    __table_args__ = (
        UniqueConstraint("request_id", "level", name="uq_request_approval_level"),
        CheckConstraint("level IN (1, 2)", name="ck_request_approval_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    request_id: Mapped[int] = mapped_column(
        ForeignKey("new_repair_devices_requests.id", ondelete="CASCADE"), nullable=False
    )

    approver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    level: Mapped[int] = mapped_column(Integer, nullable=False)

    decision: Mapped[ApprovalDecision] = mapped_column(
        enum_column(ApprovalDecision, "approval_decision"),
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    acted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships

    # The approver is a user who is responsible for approving or rejecting the request.
    approver: Mapped[User] = relationship(
        back_populates="approvals", foreign_keys=[approver_id]
    )

    # The request is the device request that is being approved or rejected.
    request: Mapped[NewRepairDevicesRequest] = relationship(
        back_populates="approvals", foreign_keys=[request_id]
    )
