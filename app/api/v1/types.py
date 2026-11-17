from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, computed_field, model_validator

from app.database.models import (
    ApprovalDecision,
    AssignmentReturnType,
    DeviceCondition,
    DeviceRequestStatus,
    DeviceRequestType,
    DeviceStatus,
    JoinRequestStatus,
    RepairStatus,
    UserRole,
)


class StatusResponse(BaseModel):
    message: str


class UserRef(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: UserRole | None = None


class DeviceRef(BaseModel):
    id: int
    name: str
    ram_gb: int
    ssd_gb: int
    hdd_gb: int
    processor: str
    brand: str
    created_at: datetime | None = None

    status: DeviceStatus
    condition: DeviceCondition


# -----------------------------
# USER ENDPOINT MODELS
# -----------------------------
class UserPartialUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class UpdatePassword(BaseModel):
    old_password: str
    new_password: str


class SignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    first_name: str = Field(min_length=3, max_length=100)
    last_name: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8)


class Setup2FAResponse(BaseModel):
    uri: str


class Activate2FARequest(BaseModel):
    code: str


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
    is_2fa_enabled: bool


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


class DevicePartialUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    ram_gb: int | None = None
    ssd_gb: int | None = None
    hdd_gb: int | None = None
    processor: str | None = None


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


class ResetDeviceAccess(BaseModel):
    device_id: int
    current_holder_id: int
    return_note: str | None = None


class _RequestApprovals(BaseModel):
    level: int
    approver_username: str
    decision: ApprovalDecision
    role: UserRole | None = None
    remarks: str | None = None
    acted_at: datetime | None = None


class AllDevicesRequestsResponse(BaseModel):
    request_id: int
    requester_info: UserRef
    requested_at: datetime
    type: DeviceRequestType
    status: DeviceRequestStatus
    device_info: DeviceRef | None = None
    requested_specs: str | None = None
    issue: str | None

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


class MyDevicesResponse(BaseModel):
    device_info: DeviceRef
    assigned_at: datetime | None = None
    condition_on_issue: DeviceCondition | None = None


class DeviceInfo(BaseModel):
    id: int
    name: str
    serial_no: str
    brand: str
    processor: str
    ram_gb: int
    ssd_gb: int
    hdd_gb: int
    status: DeviceStatus
    condition: DeviceCondition
    purchase_date: datetime | None = None
    purchase_price: float | None = None
    created_at: datetime
    updated_at: datetime


class Assignments(BaseModel):
    id: int
    request_id: int | None = None  # None = assigned directly by an admin
    assigned_to: UserRef
    assigned_by: UserRef | None = None  # None = direct assignment or a deleted user
    scheduled_at: datetime
    assigned_at: datetime | None = None

    returned_by: UserRef | None
    return_type: AssignmentReturnType | None = None
    return_note: str | None = None
    returned_at: datetime | None = None
    condition_on_issue: DeviceCondition | None = None
    condition_on_return: DeviceCondition | None = None

    @computed_field
    @property
    def state(self) -> Literal["scheduled", "active", "returned", "revoked"]:
        if self.return_type:
            return self.return_type.value

        return "active" if self.assigned_at else "scheduled"


class Repairs(BaseModel):
    id: int
    request_id: int
    requested_by: UserRef
    issue: str | None = None  # what the user reported (from the request)
    note: str  # the admin/supervisor's remarks when approving
    status: RepairStatus
    requested_at: datetime
    scheduled_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def is_active(self) -> bool:
        return self.status in (RepairStatus.SCHEDULED, RepairStatus.IN_PROGRESS)


class HistorySummary(BaseModel):
    total_assignments: int
    total_repairs: int
    current_holder: UserRef | None = None  # who has it right now
    under_repair: bool


class DevicesHistory(BaseModel):
    device_info: DeviceInfo
    summary: HistorySummary

    # newest first
    repairs: list[Repairs]
    assignments: list[Assignments]


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


# -----------------------------
# TRANSCRIBE ENDPOINT MODELS
# -----------------------------
class ProcessStartResponse(BaseModel):
    task_id: str
    message: str = "Process started..."


class VoiceFields(BaseModel):
    name: str | None = None
    brand: str | None = None
    serial_no: str | None = None
    processor: str | None = None
    ram_gb: int | None = None
    ssd_gb: int | None = None
    hdd_gb: int | None = None
    purchase_date: str | None = None  # "YYYY-MM-DD"
    purchase_price: float | None = None


class ReviewNote(BaseModel):
    field: str
    reason: str


class VoiceDeviceRecord(BaseModel):
    status: Literal["complete", "incomplete", "not_a_device_description"]
    fields: VoiceFields
    missing_fields: list[str] = []
    needs_review: list[ReviewNote] = []
    follow_up_question: str | None = None


class CeleryTranscribeResult(BaseModel):
    task_id: str | None = None
    status: str = "Sucess"
    result: VoiceDeviceRecord | None = None
    developer_error: str | None = None
