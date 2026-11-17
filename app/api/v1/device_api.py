from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.types import (
    AddDeviceRequest,
    AllDevicesRequestsResponse,
    Assignments,
    DeviceHistorySort,
    DeviceInfo,
    DevicePartialUpdate,
    DeviceRef,
    DeviceSearchSort,
    DevicesHistory,
    HistorySummary,
    MakeDeviceRequest,
    MyDevicesResponse,
    ProcessDeviceRequest,
    Repairs,
    ResetDeviceAccess,
    SearchOptionsResponse,
    StatusResponse,
    _RequestApprovals,
)
from app.api.v1.utils import _user_ref
from app.database.models import (
    ApprovalDecision,
    AssignmentReturnType,
    Device,
    DeviceAssignment,
    DeviceCondition,
    DeviceRepair,
    DeviceRequestStatus,
    DeviceRequestType,
    DevicesRequest,
    DeviceStatus,
    RequestApproval,
    SupervisorDeveloper,
    User,
    UserRole,
)
from app.dependencies import DBSession, GetCurrentUser
from app.services import EmailManager
from app.services.tasks_manager import (
    process_scheduled_device_request,
    send_device_scheduled_reminder_alert,
)


class DeviceAPI:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/device", tags=["Device Endpoint"])
        self._register_routes()
        self.email_manager = EmailManager()

    def _register_routes(self) -> None:

        # Search devices by options
        self.router.add_api_route(
            "/options",
            endpoint=self.get_search_options,
            methods=["GET"],
            response_model=SearchOptionsResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/search",
            endpoint=self.search_devices,
            methods=["GET"],
            response_model=list[DeviceRef],
            status_code=status.HTTP_200_OK,
        )

        # Devices currently hold by Superbers/developers
        self.router.add_api_route(
            "/my-devices",
            endpoint=self.get_my_devices,
            methods=["GET"],
            response_model=list[MyDevicesResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/history",
            endpoint=self.get_devices_history,
            methods=["GET"],
            response_model=list[DevicesHistory],
            status_code=status.HTTP_200_OK,
        )

        # Device CRUD
        self.router.add_api_route(
            "",
            endpoint=self.add_device,
            methods=["POST"],
            response_model=StatusResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "",
            endpoint=self.update_device,
            methods=["PATCH"],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "",
            endpoint=self.delete_device,
            methods=["DELETE"],
            status_code=status.HTTP_200_OK,
        )

        # Request CRUD
        self.router.add_api_route(
            "/reset-access",
            endpoint=self.reset_device_access,
            methods=["PATCH"],
            response_model=StatusResponse,
            status_code=status.HTTP_200_OK,
        )

        self.router.add_api_route(
            "/create-request",
            endpoint=self.create_device_request,
            methods=["POST"],
            response_model=StatusResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/all-requests",
            endpoint=self.get_devices_requests,
            methods=["GET"],
            response_model=list[AllDevicesRequestsResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/process-request",
            endpoint=self.process_device_request,
            methods=["POST"],
            response_model=StatusResponse,
            status_code=status.HTTP_200_OK,
        )

    def _device_ref(self, d: Device | None) -> DeviceRef | None:
        return (
            DeviceRef(
                id=d.id,
                name=d.name,
                ram_gb=d.ram_gb,
                hdd_gb=d.hdd_gb,
                ssd_gb=d.ssd_gb,
                processor=d.processor,
                brand=d.brand,
                status=d.status,
                condition=d.condition,
                created_at=d.created_at,
            )
            if d
            else None
        )

    async def get_search_options(self) -> SearchOptionsResponse:
        return SearchOptionsResponse(
            statuses=list(DeviceStatus),
            conditions=list(DeviceCondition),
        )

    async def get_devices_requests(
        self,
        user: GetCurrentUser,
        session: DBSession,
        type: Annotated[DeviceRequestType | None, Query()] = None,
        status: Annotated[DeviceRequestStatus | None, Query()] = None,
        my_developers_requests: Annotated[bool, Query()] = False,
    ) -> list[AllDevicesRequestsResponse]:
        resp_data: list[AllDevicesRequestsResponse] = []

        if my_developers_requests and user.role != UserRole.SUPERVISOR:
            raise HTTPException(
                status_code=400,
                detail="You don't have any developers!",
            )

        devices_requests: Sequence[DevicesRequest] = []

        filters = []

        if type:
            filters.append(DevicesRequest.type == type)

        if status:
            filters.append(DevicesRequest.status == status)

        # ADMIN: can see everyone's requests and their level of approvals
        if user.role == UserRole.ADMIN:
            result = await session.scalars(
                select(DevicesRequest)
                .options(
                    selectinload(DevicesRequest.device),
                    selectinload(DevicesRequest.approvals).selectinload(
                        RequestApproval.approver
                    ),
                    selectinload(DevicesRequest.requester),
                )
                .where(*filters)
            )
            devices_requests = result.all()

        # SUPERVISOR with my_developers(True): Supervisor can only see their developers requests
        elif my_developers_requests and user.role == UserRole.SUPERVISOR:
            result = await session.scalars(
                select(DevicesRequest)
                .options(
                    selectinload(DevicesRequest.device),
                    selectinload(DevicesRequest.approvals).selectinload(
                        RequestApproval.approver
                    ),
                    selectinload(DevicesRequest.requester),
                )
                .where(RequestApproval.approver_id == user.id, *filters)
            )
            devices_requests = result.all()

        # SUPERVISOR/DEVELOPER: can only see their own requests
        elif user.role == UserRole.SUPERVISOR or user.role == UserRole.DEVELOPER:
            result = await session.scalars(
                select(DevicesRequest)
                .options(
                    selectinload(DevicesRequest.device),
                    selectinload(DevicesRequest.approvals).selectinload(
                        RequestApproval.approver
                    ),
                    selectinload(DevicesRequest.requester),
                )
                .where(DevicesRequest.requested_by == user.id, *filters)
            )

            devices_requests = result.all()

        else:
            raise HTTPException(
                status_code=400,
                detail="Not a valid request, please contact admin.",
            )

        for device_request in devices_requests:
            approvals: list[_RequestApprovals] = []

            for approval in device_request.approvals:
                approvals.append(
                    _RequestApprovals(
                        level=approval.level,
                        role=approval.approver.role if approval.approver.role else None,
                        approver_username=approval.approver.username,
                        decision=approval.decision,
                        remarks=approval.remarks,
                        acted_at=approval.acted_at,
                    )
                )

            resp_data.append(
                AllDevicesRequestsResponse(
                    request_id=device_request.id,
                    requester_info=_user_ref(device_request.requester),  # type: ignore
                    requested_at=device_request.requested_at,
                    type=device_request.type,
                    status=device_request.status,
                    device_info=self._device_ref(device_request.device),
                    requested_specs=device_request.requested_specs,
                    issue=device_request.issue,
                    approvals=approvals,
                )
            )
        return resp_data

    async def get_devices_history(
        self,
        user: GetCurrentUser,
        session: DBSession,
        sort_by: Annotated[DeviceHistorySort, Query()] = "name",
        status: Annotated[DeviceStatus | None, Query()] = None,
    ) -> list[DevicesHistory]:
        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Admins only")

        filters = []

        if status is not None:
            filters.append(Device.status == status)

        devices = await session.scalars(
            select(Device)
            .options(
                selectinload(Device.assignments).options(
                    selectinload(DeviceAssignment.assigned_to_user),
                    selectinload(DeviceAssignment.assigned_by_user),
                    selectinload(DeviceAssignment.returned_by_user),
                ),
                selectinload(Device.repairs)
                .selectinload(DeviceRepair.request)
                .selectinload(DevicesRequest.requester),
            )
            .where(*filters)
        )
        devices_history: list[DevicesHistory] = []

        for d in devices:
            device_info = DeviceInfo(
                id=d.id,
                name=d.name,
                serial_no=d.serial_no,
                brand=d.brand,
                processor=d.processor,
                ram_gb=d.ram_gb,
                ssd_gb=d.ssd_gb,
                hdd_gb=d.hdd_gb,
                status=d.status,
                condition=d.condition,
                purchase_date=d.purchase_date,
                purchase_price=d.purchase_price,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )

            assignments = [
                Assignments(
                    id=a.id,
                    request_id=a.request_id,
                    assigned_to=_user_ref(a.assigned_to_user),  # type: ignore
                    assigned_by=_user_ref(a.assigned_by_user),
                    scheduled_at=a.scheduled_at,
                    assigned_at=a.assigned_at,
                    returned_by=_user_ref(a.returned_by_user),
                    return_type=a.return_type,
                    return_note=a.return_note,
                    returned_at=a.returned_at,
                    condition_on_issue=a.condition_on_issue,
                    condition_on_return=a.condition_on_return,
                )
                for a in sorted(
                    d.assignments, key=lambda a: a.scheduled_at, reverse=True
                )
            ]

            repairs = [
                Repairs(
                    id=r.id,
                    request_id=r.request_id,
                    requested_by=_user_ref(r.request.requester),  # type: ignore
                    issue=r.request.issue,
                    note=r.note,
                    status=r.status,
                    requested_at=r.requested_at,
                    scheduled_at=r.scheduled_at,
                    completed_at=r.completed_at,
                )
                for r in sorted(d.repairs, key=lambda r: r.requested_at, reverse=True)
            ]

            history_summary = HistorySummary(
                total_assignments=len(assignments),
                total_repairs=len(repairs),
                current_holder=next(
                    (a.assigned_to for a in assignments if a.state == "active"), None
                ),
                under_repair=any(r.is_active for r in repairs),
            )

            devices_history.append(
                DevicesHistory(
                    device_info=device_info,
                    summary=history_summary,
                    repairs=repairs,
                    assignments=assignments,
                )
            )

        sort_options = {
            "name": lambda d: d.device_info.name.lower(),
            "recently_updated": lambda d: d.device_info.updated_at,
            "most_assignments": lambda d: d.summary.total_assignments,
            "most_repairs": lambda d: d.summary.total_repairs,
        }

        return sorted(
            devices_history, key=sort_options[sort_by], reverse=sort_by != "name"
        )

    async def _add_device_record(
        self,
        payload: AddDeviceRequest,
        session: DBSession,
        status: DeviceStatus = DeviceStatus.AVAILABLE,
    ) -> Device:
        device = Device(
            name=payload.name,
            serial_no=payload.serial_no,
            ram_gb=payload.ram_gb,
            ssd_gb=payload.ssd_gb,
            hdd_gb=payload.hdd_gb,
            processor=payload.processor,
            brand=payload.brand,
            purchase_date=payload.purchase_date,
            status=status,
        )

        session.add(device)

        # Keep commit outside this func, don't accidently commit the on-going transection.
        await session.flush()

        return device

    async def search_devices(
        self,
        _: GetCurrentUser,
        session: DBSession,
        sort_by: Annotated[DeviceSearchSort, Query()] = "name",
        status: Annotated[DeviceStatus | None, Query()] = None,
        condition: Annotated[DeviceCondition | None, Query()] = None,
    ) -> list[DeviceRef]:

        filters = []

        if status:
            filters.append(Device.status == status)

        if condition:
            filters.append(Device.condition == condition)

        result = await session.scalars(select(Device).where(*filters))

        available_devices = result.all()

        devices = [self._device_ref(device) for device in available_devices]

        sort_options = {
            "name": lambda d: d.name.lower(),
            "brand": lambda d: d.brand.lower(),
            "ram_h_to_l": lambda d: d.ram_gb,
            "recently_added": lambda d: d.created_at,
        }
        is_reverse = sort_by in ("ram_h_to_l", "recently_added")

        return sorted(devices, key=sort_options[sort_by], reverse=is_reverse)  # type: ignore

    async def get_my_devices(
        self, user: GetCurrentUser, session: DBSession
    ) -> list[MyDevicesResponse]:
        results = await session.scalars(
            select(DeviceAssignment)
            .options(selectinload(DeviceAssignment.device))
            .where(
                DeviceAssignment.assigned_to == user.id,
                DeviceAssignment.returned_at.is_(None),
            )
        )
        device_assignments = results.all()
        devices: list[MyDevicesResponse] = []

        for da in device_assignments:
            device = da.device
            if device.status == DeviceStatus.ASSIGNED:
                devices.append(
                    MyDevicesResponse(
                        device_info=DeviceRef(
                            id=device.id,
                            name=device.name,
                            ram_gb=device.ram_gb,
                            ssd_gb=device.ssd_gb,
                            hdd_gb=device.hdd_gb,
                            processor=device.processor,
                            brand=device.brand,
                            status=device.status,
                            condition=device.condition,
                            created_at=device.created_at,
                        ),
                        assigned_at=da.assigned_at,
                        condition_on_issue=da.condition_on_issue,
                    )
                )

        return devices

    async def add_device(
        self,
        payload: AddDeviceRequest,
        user: GetCurrentUser,
        session: DBSession,
    ) -> StatusResponse:

        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin only!"
            )

        await self._add_device_record(payload, session)

        await session.commit()

        return StatusResponse(
            message="Device has been added to the inventory and available for use."
        )

    async def update_device(
        self,
        device_id: Annotated[int, Query(...)],
        payload: DevicePartialUpdate,
        user: GetCurrentUser,
        session: DBSession,
    ):
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin only!"
            )

        device = await session.get(Device, device_id)

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )

        update_data = payload.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(device, field, value)

        await session.commit()

    async def delete_device(
        self,
        device_id: Annotated[int, Query(...)],
        user: GetCurrentUser,
        session: DBSession,
    ):
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin only!"
            )

        device = await session.scalar(select(Device).where(Device.id == device_id))

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found!"
            )

        if device.status != DeviceStatus.AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device isn't free.",
            )

        await session.delete(device)
        await session.commit()

    async def reset_device_access(
        self,
        payload: ResetDeviceAccess,
        user: GetCurrentUser,
        session: DBSession,
    ) -> StatusResponse:
        # The one active assignment of this device (the partial unique index allows at most one).
        assignment = await session.scalar(
            select(DeviceAssignment)
            .options(
                selectinload(DeviceAssignment.device),
                selectinload(DeviceAssignment.assigned_to_user),
            )
            .where(
                DeviceAssignment.device_id == payload.device_id,
                DeviceAssignment.assigned_to == payload.current_holder_id,
                DeviceAssignment.returned_at.is_(None),
            )
            .with_for_update()  # add low-level lock; preventing race-conditions
        )

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active assignment found for this device and holder. It may already have been returned or revoked.",
            )

        if assignment.assigned_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This device hasn't been handed over yet, so there is no access to revoke.",
            )

        holder = assignment.assigned_to_user
        device = assignment.device
        is_holder = holder.id == user.id

        # Frontend is not yet configured for supvervisor controlling their developer's devices access
        # Allowed: the holder (a return), an admin, or the holder's supervisor (a revoke).
        if not is_holder and user.role != UserRole.ADMIN:
            is_their_developer = (
                user.role == UserRole.SUPERVISOR
                and await session.scalar(
                    select(SupervisorDeveloper.id).where(
                        SupervisorDeveloper.developer_id == holder.id,
                        SupervisorDeveloper.supervisor_id == user.id,
                    )
                )
            )
            if not is_their_developer:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You aren't authorized to revoke this access.",
                )

        assignment.returned_at = datetime.now(UTC)
        assignment.returned_by = user.id
        assignment.return_type = (
            AssignmentReturnType.RETURNED if is_holder else AssignmentReturnType.REVOKED
        )
        assignment.return_note = payload.return_note
        assignment.condition_on_return = device.condition

        # Free the device.
        if device.status == DeviceStatus.ASSIGNED:
            device.status = DeviceStatus.AVAILABLE

        await session.commit()

        return StatusResponse(
            message="Device returned."
            if is_holder
            else f"Access revoked from {holder.username}."
        )

    async def create_device_request(
        self,
        payload: MakeDeviceRequest,
        user: GetCurrentUser,
        session: DBSession,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> StatusResponse:

        if user.role == UserRole.ADMIN:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(
                message="Sorry, you're admin and can't create device request. Please add device directly to inventory"
            )

        if payload.type == DeviceRequestType.REPAIR:
            active_assignment = await session.scalar(
                select(DeviceAssignment).where(
                    DeviceAssignment.assigned_to == user.id,
                    DeviceAssignment.device_id == payload.device_id,
                    DeviceAssignment.returned_at.is_(None),
                )
            )

            if not active_assignment:
                response.status_code = status.HTTP_403_FORBIDDEN
                return StatusResponse(
                    message="The device you're requesting a repair for, doesn't belongs to you, please contact admin."
                )

        device: Device | None = None

        if payload.type == DeviceRequestType.EXISTING:
            device = await session.get(Device, payload.device_id)

            if device and device.status != DeviceStatus.AVAILABLE:
                response.status_code = status.HTTP_400_BAD_REQUEST
                return StatusResponse(
                    message="The device is not available for assignments."
                )

        # Fetch Admin; it's required for approval at any level
        admin_user = await session.scalar(
            select(User).where(User.role == UserRole.ADMIN)
        )

        if not admin_user:
            response.status_code = status.HTTP_404_NOT_FOUND
            return StatusResponse(message="Admin not found.")

        device_request = DevicesRequest(
            requested_by=user.id,
            issue=payload.issue,
            type=payload.type,
        )

        if payload.type == DeviceRequestType.NEW:
            device_request.requested_specs = payload.requested_specs
        else:
            device_request.device_id = payload.device_id

        current_approver: str | None = None

        if user.role == UserRole.SUPERVISOR:
            device_request.pending_by = admin_user.id
            device_request.requested_specs = payload.requested_specs

            # Inform Admin through Email notification
            current_approver = admin_user

            approvals = [RequestApproval(approver_id=admin_user.id, level=2)]

        elif user.role == UserRole.DEVELOPER and user.supervisor_assignment:
            # Fetch Developer's Supervisor id first to whom the request should be sent
            supervisor_id = user.supervisor_assignment.supervisor_id

            device_request.pending_by = supervisor_id
            device_request.device_id = payload.device_id

            # Intentionally, only to complete task quickly

            current_approver = await session.get(User, supervisor_id)

            approvals = [
                RequestApproval(approver_id=supervisor_id, level=1),
                RequestApproval(approver_id=admin_user.id, level=2),
            ]

        else:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(
                message="DEVELOPER: Request can't be created. Please contact admin!"
            )

        session.add(device_request)
        await session.flush()

        for approval in approvals:
            approval.request_id = device_request.id

        session.add_all(approvals)

        await session.commit()

        # Notify current approver
        if current_approver:
            print(f"sending email to {current_approver.email}...")
            background_tasks.add_task(
                self.email_manager.send_device_request_notification,
                to_email=current_approver.email,
                approver_username=current_approver.username,
                requester_username=user.username,
                requester_name=f"{user.first_name} {user.last_name}",
                request_id=device_request.id,
                request_type=device_request.type.value,
                requested_at=device_request.requested_at,
                device_name=device.name if device else None,
                device_serial=device.serial_no if device else None,
                requested_specs=payload.requested_specs,
            )

        decision_msg = (
            "your supervisor" if user.role == UserRole.DEVELOPER else "the admin"
        )

        return StatusResponse(
            message=f"Request has been sent to {decision_msg} for approval."
        )

    async def process_device_request(
        self,
        payload: ProcessDeviceRequest,
        user: GetCurrentUser,
        session: DBSession,
        response: Response,
        background_tasks: BackgroundTasks,
    ):
        # Developers are the lowest in rank and not allowed to process any kind of device requests
        if user.role == UserRole.DEVELOPER:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(
                message="You are not authorized to approve this request."
            )

        request_approval_record = await session.scalar(
            select(RequestApproval).where(
                RequestApproval.request_id == payload.request_id,
                RequestApproval.approver_id == user.id,
            )
        )

        if not request_approval_record:
            response.status_code = status.HTTP_403_FORBIDDEN
            return StatusResponse(message="Request not found.")

        if request_approval_record.decision != ApprovalDecision.PENDING:
            return StatusResponse(
                message=f"Request has already been {request_approval_record.decision.value}."
            )

        decision = (
            ApprovalDecision.APPROVED if payload.grant else ApprovalDecision.REJECTED
        )

        request_approval_record.decision = decision
        request_approval_record.remarks = payload.remarks
        request_approval_record.acted_at = datetime.now(UTC)

        # Fetch main request record by request id and current user id
        devices_request_record = await session.scalar(
            select(DevicesRequest)
            .options(
                selectinload(DevicesRequest.requester),
                selectinload(DevicesRequest.device),
            )
            .where(
                DevicesRequest.id == payload.request_id,
                DevicesRequest.pending_by == user.id,
            )
        )

        if not devices_request_record:
            response.status_code = status.HTTP_409_CONFLICT
            return StatusResponse(
                message=(
                    "This request has either already been processed by you or is awaiting approval from a lower-level authority."
                )
            )

        if devices_request_record.status == DeviceRequestStatus.REJECTED:
            return StatusResponse(message="Request has already been rejected.")

        elif devices_request_record.status == DeviceRequestStatus.APPROVED:
            return StatusResponse(message="Request has already been approved by amdin.")

        elif devices_request_record.status == DeviceRequestStatus.FULFILLED:
            return StatusResponse(
                message="Request has already been approved and fulfilled by amdin."
            )

        if (
            payload.grant
            and user.role == UserRole.ADMIN
            and devices_request_record.type == DeviceRequestType.NEW
            and (not payload.device_specs or not payload.scheduled_at)
        ):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return StatusResponse(
                message="Please provide all required details (device_specs, scheduled_at) to approve request for a new device."
            )

        next_request_approval: RequestApproval | None = None
        device: Device | None = None

        if decision == ApprovalDecision.REJECTED:
            devices_request_record.status = DeviceRequestStatus.REJECTED

        elif payload.grant:
            # It's a last level, approve the NewRepairDevicesRequest.status, update neccessary info and return
            if user.role == UserRole.ADMIN:
                devices_request_record.status = DeviceRequestStatus.APPROVED

                if (
                    devices_request_record.device
                    and devices_request_record.type == DeviceRequestType.REPAIR
                ):
                    device = devices_request_record.device
                    # For now there is no one to tell when will the requester received the repaired device. Admin can only set the scheduled time
                    # So set device.status to 'Repair' here and to 'Assigned' in process_scheduled_device_request task.
                    device.status = DeviceStatus.REPAIR

                    device_repair = DeviceRepair(
                        device_id=device.id,
                        note=payload.remarks or "",
                        request_id=payload.request_id,
                        scheduled_at=payload.scheduled_at,
                        requested_by=devices_request_record.requested_by,
                        requested_at=devices_request_record.requested_at,
                    )

                    session.add(device_repair)
                    await session.flush()

                else:
                    if (
                        devices_request_record.device
                        and devices_request_record.type == DeviceRequestType.EXISTING
                    ):
                        device = devices_request_record.device
                        device.status = DeviceStatus.RESERVED

                        device_assignment = DeviceAssignment(
                            device_id=device.id,
                            request_id=payload.request_id,
                            assigned_to=devices_request_record.requested_by,
                            assigned_by=user.id,
                            scheduled_at=payload.scheduled_at,
                        )

                        session.add(device_assignment)
                        await session.flush()

                    elif (
                        payload.device_specs
                        and devices_request_record.type == DeviceRequestType.NEW
                    ):
                        device = await self._add_device_record(
                            payload.device_specs,
                            session,
                            status=DeviceStatus.RESERVED,  # Update this on-schedule
                        )

                        session.add(device)
                        await session.flush()

                        # Link the new device to the request
                        devices_request_record.device_id = device.id

                        device_assignment = DeviceAssignment(
                            device_id=device.id,
                            request_id=payload.request_id,
                            assigned_to=devices_request_record.requested_by,
                            assigned_by=user.id,
                            scheduled_at=payload.scheduled_at,
                            condition_on_issue=DeviceCondition.NEW,
                        )

                        session.add(device_assignment)
                        await session.flush()

            else:  # Find next approval, update NewRepairDevicesRequest.pending_by with that approval.id, and send a email notification to both pending approval and requester
                next_request_approval = await session.scalar(
                    select(RequestApproval)
                    .options(selectinload(RequestApproval.approver))
                    .where(RequestApproval.level == request_approval_record.level + 1)
                )

                if next_request_approval:
                    devices_request_record.pending_by = (
                        next_request_approval.approver_id
                    )

                else:
                    response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                    return StatusResponse(
                        message="Your request was processed successfully, but the next approver could not be identified. All changes have been rolled back. Please contact the admin for assistance."
                    )

        await session.commit()

        background_tasks.add_task(
            self.email_manager.send_device_request_decision,
            to_email=devices_request_record.requester.email,
            request_id=devices_request_record.id,
            device_name=devices_request_record.device.name
            if devices_request_record.device
            else "Unknown",
            approved=payload.grant,
            approver_username=request_approval_record.approver.username,
            approver_role=request_approval_record.approver.role.value or "Unknown",  # type: ignore
            remarks=payload.remarks,
            next_approver_username=next_request_approval.approver.username
            if next_request_approval
            else None,
            next_approver_role=next_request_approval.approver.role.value  # type: ignore
            if next_request_approval
            else None,
            scheduled_at=payload.scheduled_at if payload.scheduled_at else None,
        )

        if next_request_approval:
            background_tasks.add_task(
                self.email_manager.send_device_request_notification,
                to_email=next_request_approval.approver.email,
                approver_username=next_request_approval.approver.username,
                requester_username=user.username,
                requester_name=f"{user.first_name} {user.last_name}",
                request_id=devices_request_record.id,
                request_type=devices_request_record.type.value,
                requested_at=devices_request_record.requested_at,
                device_name=devices_request_record.device.name
                if devices_request_record.device
                else None,
                device_serial=devices_request_record.device.serial_no
                if devices_request_record.device
                else None,
                requested_specs=devices_request_record.requested_specs,
            )

        if device and payload.scheduled_at:
            now = datetime.now(UTC)
            scheduled_at = payload.scheduled_at

            # Reminder: 12 hours before scheduled time
            reminder_at = scheduled_at - timedelta(hours=12)

            reminder_countdown = max(0, int((reminder_at - now).total_seconds()))

            send_device_scheduled_reminder_alert.apply_async(  # type: ignore
                kwargs={
                    "to_email": devices_request_record.requester.email,
                    "requester_username": devices_request_record.requester.username,
                    "request_id": payload.request_id,
                    "request_type": devices_request_record.type,
                    "device_name": device.name,
                    "device_serial": device.serial_no,
                    "scheduled_at": payload.scheduled_at,
                },
                countdown=reminder_countdown,
            )
            # Process records: at scheduled time
            process_countdown = max(0, int((scheduled_at - now).total_seconds()))
            process_scheduled_device_request.apply_async(  # type: ignore
                kwargs={"request_id": payload.request_id}, countdown=process_countdown
            )

        return StatusResponse(message=f"Request {decision.value} successful.")
