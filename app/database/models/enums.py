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
    NEW = "new"  # No repair
    GOOD = "good"  # 1 Repair
    FAIR = "fair"  # 2-3 Repairs
    POOR = "poor"  # 4+ Repairs


class DeviceRequestType(str, Enum):
    NEW = "new"
    EXISTING = "existing"
    REPAIR = "repair"


class DeviceRequestStatus(str, Enum):
    PENDING = "pending"
    REJECTED = "rejected"
    APPROVED = "approved"
    REVOKED = "revoked"
    FULFILLED = "fulfilled"


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class RepairStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"  # should be removed; no purpose
    COMPLETED = "completed"


class AssignmentReturnType(str, Enum):
    RETURNED = "returned"  # the device was handed back
    REVOKED = "revoked"  # admin/supervisor took it back
