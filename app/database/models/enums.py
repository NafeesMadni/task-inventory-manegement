from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    DEVELOPER = "developer"


class JoinRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeviceStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    ASSIGNED = "assigned"
    REPAIR = "repair"
    RETIRED = "retired"


class DeviceCondition(str, Enum):
    NEW = "new"
    FAIR = "fair"
    GOOD = "good"
    POOR = "poor"


class DeviceRequestType(str, Enum):
    NEW = "new"
    EXISTING = "existing"
    REPAIR = "repair"


class DeviceRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RepairStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
