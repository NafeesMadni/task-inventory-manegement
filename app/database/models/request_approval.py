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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, enum_check_constraint, enum_column
from app.database.models.enums import ApprovalDecision

if TYPE_CHECKING:
    from app.database.models import DevicesRequest, User


class RequestApproval(Base):
    __tablename__ = "request_approvals"

    __table_args__ = (
        UniqueConstraint("request_id", "level", name="uq_request_approval_level"),
        UniqueConstraint(
            "request_id", "approver_id", name="uq_request_approval_approver"
        ),
        CheckConstraint("level IN (1, 2)", name="ck_request_approval_level"),
        enum_check_constraint(
            ApprovalDecision, "decision", "ck_request_approvals_decision"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    request_id: Mapped[int] = mapped_column(
        ForeignKey("devices_requests.id", ondelete="CASCADE"), nullable=False
    )

    approver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    level: Mapped[int] = mapped_column(Integer, nullable=False)

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    decision: Mapped[ApprovalDecision] = mapped_column(
        enum_column(ApprovalDecision, "approval_decision"),
        default=ApprovalDecision.PENDING,
        nullable=False,
    )

    # Update when request decision is made either APPROVED/REJECTED; empty on PENDING
    acted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships

    # The approver is a user who is responsible for approving or rejecting the request.
    approver: Mapped[User] = relationship(
        back_populates="approvals", foreign_keys=[approver_id]
    )

    # The request is the device request that is being approved or rejected.
    request: Mapped[DevicesRequest] = relationship(
        back_populates="approvals", foreign_keys=[request_id]
    )
