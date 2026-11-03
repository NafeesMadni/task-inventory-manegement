from __future__ import annotations

from app.database.models.base import Base, enum_check_constraint, enum_column
from app.database.models.device import Device
from app.database.models.device_assignment import DeviceAssignment
from app.database.models.device_repair import DeviceRepair
from app.database.models.device_request import NewRepairDevicesRequest
from app.database.models.enums import (
    ApprovalDecision,
    DeviceCondition,
    DeviceRequestStatus,
    DeviceRequestType,
    DeviceStatus,
    JoinRequestStatus,
    RepairStatus,
    UserRole,
)
from app.database.models.join_request import JoinRequest
from app.database.models.login_history import LoginHistory
from app.database.models.request_approval import RequestApproval
from app.database.models.supervisor_developer import SupervisorDeveloper
from app.database.models.user import User, get_user_loading_options

__all__ = [
    "ApprovalDecision",
    "Base",
    "Device",
    "DeviceAssignment",
    "DeviceCondition",
    "DeviceRepair",
    "DeviceRequestStatus",
    "DeviceRequestType",
    "DeviceStatus",
    "JoinRequest",
    "JoinRequestStatus",
    "LoginHistory",
    "NewRepairDevicesRequest",
    "RepairStatus",
    "RequestApproval",
    "SupervisorDeveloper",
    "User",
    "UserRole",
    "enum_check_constraint",
    "enum_column",
    "get_user_loading_options",
]
