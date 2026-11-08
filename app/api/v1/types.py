from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.database.models import (
    DeviceRequestType,
    JoinRequestStatus,
    UserRole,
)
from app.database.models.enums import (
    ApprovalDecision,
    DeviceCondition,
    DeviceRequestStatus,
)


class StatusResponse(BaseModel):
    message: str


# -----------------------------
# USER ENDPOINT MODELS
# -----------------------------
class SignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    first_name: str = Field(min_length=3, max_length=100)
    last_name: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8)
    requested_role: UserRole = Field(default=UserRole.DEVELOPER)
    requested_from: int | None = Field(
        default=None
    )  # only for developer role, this is the supervisor id
    request_note: str | None = Field(default=None)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr


class SupervisorResponse(BaseModel):
    id: int
    username: str


class JoinRequestsResponse(BaseModel):
    id: int
    requested_role: UserRole
    requested_by: int
    requested_from: int
    request_note: str | None
    status: JoinRequestStatus
    requested_at: datetime
    processed_by: int | None
    processed_at: datetime | None
    processed_reason: str | None


# -----------------------------
# DEVICE ENDPOINT MODELS
# -----------------------------
class _AddDeviceRequest(BaseModel):
    name: str
    serial_no: str
    ram_gb: int
    ssd_gb: int
    hdd_gb: int
    processor: str
    brand: str
    purchase_date: datetime
    purchase_price: float


class ProcessDeviceRequest(BaseModel):
    request_id: int
    remarks: str | None = None
    grant: bool = True

    # For Admin Only
    scheduled_at: datetime | None = None

    # For new device approval by admin
    device_specs: _AddDeviceRequest | None = None

    @model_validator(mode="after")
    def check_specs_for_rejection(self) -> ProcessDeviceRequest:
        # Check if not granted and device_specs is provided
        if not self.grant and self.device_specs is not None:
            raise ValueError(
                "device_specs must be None when the decision selected as rejected."
            )
        return self


class _RequestApprovals(BaseModel):
    level: int
    approver_username: str
    decision: ApprovalDecision
    role: UserRole | None = None
    remarks: str | None = None
    acted_at: datetime | None = None


class AllDevicesRequestsResponse(BaseModel):
    request_id: int
    requested_at: datetime
    type: DeviceRequestType
    status: DeviceRequestStatus
    device_id: int | None = None
    requested_specs: str | None = None

    approvals: list[_RequestApprovals]


class MakeDeviceRequest(BaseModel):
    type: DeviceRequestType

    # Only for DeviceRequestType.EXISTING | DeviceRequestType.REPAIR
    # For DeviceRequestType.REPAIR, check device assignment whether this device is in used by this requester?
    device_id: int | None = None

    # Only for DeviceRequestType.NEW
    requested_specs: str | None = None


class AvailableDevicesResponse(BaseModel):
    id: int
    name: str
    ram_gb: int
    ssd_gb: int
    hdd_gb: int
    processor: str
    brand: str
    issued_at: datetime | None = None
    condition: DeviceCondition


class AssignedByDevicesResponse(BaseModel):
    id: int
    device_id: int
    status_fullfilled: bool
    assigned_to: bool
    assigned_at: datetime | None
