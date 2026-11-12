from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.database.models import (
    ApprovalDecision,
    DeviceCondition,
    DeviceRequestStatus,
    DeviceRequestType,
    DeviceStatus,
    JoinRequestStatus,
    UserRole,
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


class CreateJoinReqRequest(BaseModel):
    requested_role: UserRole = Field(default=UserRole.DEVELOPER)
    requested_from: int
    request_note: str | None = Field(default=None)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    username: str
    role: UserRole | None
    email: EmailStr


class AuthResponse(BaseModel):
    message: str
    redirect_url: str | None = None


class ActiveApprovalsResponse(BaseModel):
    id: int
    username: str
    role: UserRole


class LoginHistoryResponse(BaseModel):
    username: str
    ip: str | None = None
    role: UserRole | None = None
    logged_in_at: datetime
    logged_out_at: datetime | None = None


class JoinRequestsResponse(BaseModel):
    id: int
    requester_role: UserRole
    requester_username: str
    approval_role: UserRole
    approval_username: str
    request_note: str | None
    status: JoinRequestStatus
    requested_at: datetime
    processed_by_username: str | None
    processed_by_role: UserRole | None
    processed_at: datetime | None


# -----------------------------
# DEVICE ENDPOINT MODELS
# -----------------------------
class AddDeviceRequest(BaseModel):
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
    device_specs: AddDeviceRequest | None = None

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
    requester_username: str
    requested_at: datetime
    type: DeviceRequestType
    status: DeviceRequestStatus
    device_id: int | None = None
    requested_specs: str | None = None

    approvals: list[_RequestApprovals]


class MakeDeviceRequest(BaseModel):
    type: DeviceRequestType

    issue: str

    # Required for EXISTING and REPAIR
    device_id: int | None = None

    # Required for NEW
    requested_specs: str | None = None

    @model_validator(mode="after")
    def validate_request(self):
        if (
            self.type in (DeviceRequestType.EXISTING, DeviceRequestType.REPAIR)
            and self.device_id is None
        ):
            raise ValueError(f"device_id is required for {self.type.value} requests.")

        if self.type == DeviceRequestType.NEW and not self.requested_specs:
            raise ValueError("requested_specs is required for new device requests.")

        if self.type == DeviceRequestType.REPAIR and not self.issue.strip():
            raise ValueError("Please describe the issue with your device.")

        return self


class AvailableDevicesResponse(BaseModel):
    id: int
    name: str
    ram_gb: int
    ssd_gb: int
    hdd_gb: int
    processor: str
    brand: str
    issued_at: datetime | None = None

    status: DeviceStatus
    condition: DeviceCondition


class AssignedByDevicesResponse(BaseModel):
    id: int
    device_id: int
    status_fullfilled: bool
    assigned_to: bool
    assigned_at: datetime | None


class SearchOptionsResponse(BaseModel):
    statuses: list[DeviceStatus]
    conditions: list[DeviceCondition]


class SearchDevicesRequest(BaseModel):
    status: DeviceStatus | None = None
    condition: DeviceCondition | None = None
