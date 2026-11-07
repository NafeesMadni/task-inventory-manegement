from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.types import (
    AllDevicesRequestsResponse,
    AvailableDevicesResponse,
    MakeDeviceRequest,
    ProcessDeviceRequest,
    StatusResponse,
    _AddDeviceRequest,
    _RequestApprovals,
)
from app.database.models import (
    ApprovalDecision,
    Device,
    DeviceRepair,
    DeviceRequestStatus,
    DeviceRequestType,
    DeviceStatus,
    NewRepairDevicesRequest,
    RequestApproval,
    User,
    UserRole,
)
from app.database.models.device_assignment import DeviceAssignment
from app.dependencies import DBSession, GetCurrentUser


class DeviceAPI:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/device", tags=["Device Endpoint"])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/available",
            endpoint=self.get_available_devices,
            methods=["GET"],
            response_model=list[AvailableDevicesResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/add",
            endpoint=self.add_device,
            methods=["POST"],
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
            endpoint=self.get_all_devices_requests,
            methods=["POST"],
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

    async def get_all_devices_requests(
        self, user: GetCurrentUser, session: DBSession, response: Response
    ) -> list[AllDevicesRequestsResponse]:
        devices_requests: Sequence[NewRepairDevicesRequest] = []
        resp_data: list[AllDevicesRequestsResponse] = []

        # ADMIN: can see all requests and their approvals
        if user.role == UserRole.ADMIN:
            result = await session.scalars(
                select(NewRepairDevicesRequest).options(
                    selectinload(NewRepairDevicesRequest.approvals).selectinload(
                        RequestApproval.approver
                    ),
                )
            )
            devices_requests = result.all()

        # SUPERVISOR/Developer: can see only their own requests and approvals
        elif user.role == UserRole.SUPERVISOR or user.role == UserRole.DEVELOPER:
            result = await session.scalars(
                select(NewRepairDevicesRequest)
                .options(
                    selectinload(NewRepairDevicesRequest.approvals).selectinload(
                        RequestApproval.approver
                    ),
                )
                .where(NewRepairDevicesRequest.requested_by == user.id)
            )
            devices_requests = result.all()
        else:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return resp_data

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
                    requested_at=device_request.requested_at,
                    type=device_request.type,
                    status=device_request.status,
                    device_id=device_request.device_id,
                    requested_specs=device_request.requested_specs,
                    approvals=approvals,
                )
            )
        return resp_data

    async def _add_device_record(
        self,
        payload: _AddDeviceRequest,
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

    async def get_available_devices(
        self, _: GetCurrentUser, session: DBSession
    ) -> list[AvailableDevicesResponse]:
        result = await session.scalars(
            select(Device).where(Device.status == DeviceStatus.AVAILABLE)
        )
        available_devices = result.all()
        return [
            AvailableDevicesResponse(
                id=device.id,
                name=device.name,
                ram_gb=device.ram_gb,
                ssd_gb=device.ssd_gb,
                hdd_gb=device.hdd_gb,
                processor=device.processor,
                brand=device.brand,
                condition=device.condition,
                issued_at=device.issued_at,
            )
            for device in available_devices
        ]

    async def add_device(
        self,
        payload: _AddDeviceRequest,
        user: GetCurrentUser,
        session: DBSession,
        response: Response,
    ) -> StatusResponse:
        if user.role == UserRole.ADMIN:
            await self._add_device_record(payload, session)

            await session.commit()

            return StatusResponse(
                message="Device has been added to the inventory and available for use."
            )

        response.status_code = status.HTTP_403_FORBIDDEN
        return StatusResponse(
            message="You don't have autherority to add device to the inventory."
        )

    async def process_device_request(
        self,
        payload: ProcessDeviceRequest,
        user: GetCurrentUser,
        session: DBSession,
        response: Response,
    ):
        # Developer can't approve anyone else device request
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
            return StatusResponse(
                message="You're not authorized to approve this request."
            )

        if request_approval_record.decision != ApprovalDecision.PENDING:
            return StatusResponse(
                message=f"Request has already been {request_approval_record.decision.value}."
            )

        decision = (
            ApprovalDecision.APPROVED if payload.grant else ApprovalDecision.REJECTED
        )

        request_approval_record.remarks = payload.remarks
        request_approval_record.acted_at = datetime.now(UTC)
        request_approval_record.decision = decision

        # Fetch main request record by request id and current user id
        new_repair_devices_request_record = await session.scalar(
            select(NewRepairDevicesRequest)
            .options(
                selectinload(NewRepairDevicesRequest.requester),
                selectinload(NewRepairDevicesRequest.device),
            )
            .where(
                NewRepairDevicesRequest.id == payload.request_id,
                NewRepairDevicesRequest.pending_by == user.id,
            )
        )

        if not new_repair_devices_request_record:
            response.status_code = status.HTTP_404_NOT_FOUND
            return StatusResponse(message="Request not found.")

        if new_repair_devices_request_record.status == DeviceRequestStatus.REJECTED:
            return StatusResponse(message="Request has already been rejected.")

        elif new_repair_devices_request_record.status == DeviceRequestStatus.APPROVED:
            return StatusResponse(message="Request has already been approved by amdin.")

        elif new_repair_devices_request_record.status == DeviceRequestStatus.FULFILLED:
            return StatusResponse(
                message="Request has already been approved and fulfilled by amdin."
            )

        if (
            payload.grant
            and user.role == UserRole.ADMIN
            and new_repair_devices_request_record.type == DeviceRequestType.NEW
            and (not payload.device_specs or not payload.scheduled_at)
        ):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return StatusResponse(
                message="Please provide all required details (device_specs, scheduled_at) to approve request for a new device."
            )

        # For push notification about approve/reject
        requester_email = new_repair_devices_request_record.requester.email  # noqa: F841

        if decision == ApprovalDecision.REJECTED:
            new_repair_devices_request_record.status = DeviceRequestStatus.REJECTED

            await session.commit()

            # Notify the requester about rejection

            return StatusResponse(message="Request has been rejected.")

        elif payload.grant:
            # It's a last level, approve the NewRepairDevicesRequest.status, update neccessary info and return
            if user.role == UserRole.ADMIN:
                new_repair_devices_request_record.status = DeviceRequestStatus.APPROVED

                if (
                    new_repair_devices_request_record.device
                    and new_repair_devices_request_record.type
                    == DeviceRequestType.REPAIR
                ):
                    device = new_repair_devices_request_record.device
                    device.status = DeviceStatus.REPAIR

                    device_repair = DeviceRepair(
                        device_id=device.id,
                        request_id=payload.request_id,
                        scheduled_at=payload.scheduled_at,
                        requested_by=new_repair_devices_request_record.requested_by,
                        requested_at=new_repair_devices_request_record.requested_at,
                    )

                    session.add(device_repair)
                    await session.flush()

                else:
                    if (
                        new_repair_devices_request_record.device
                        and new_repair_devices_request_record.type
                        == DeviceRequestType.EXISTING
                    ):
                        device = new_repair_devices_request_record.device
                        device.status = DeviceStatus.RESERVED

                        session.add(device)

                    elif (
                        new_repair_devices_request_record.type == DeviceRequestType.NEW
                        and payload.device_specs
                    ):
                        device = await self._add_device_record(
                            payload.device_specs,
                            session,
                            status=DeviceStatus.RESERVED,  # Update this on-schedule
                        )

                        session.add(device)

                    await session.commit()
                    return StatusResponse(message="Request approved.")

            else:  # Find next approval, update NewRepairDevicesRequest.pending_by with that approval.id, and send a email notification to both pending approval and requester
                next_request_approval = await session.scalar(
                    select(RequestApproval)
                    .options(selectinload(RequestApproval.approver))
                    .where(RequestApproval.level == request_approval_record.level + 1)
                )

                if next_request_approval:
                    new_repair_devices_request_record.pending_by = (
                        next_request_approval.approver_id
                    )

                    session.add(new_repair_devices_request_record)
                    await session.commit()

                    # Notify the next approval
                    email = next_request_approval.approver.email  # noqa: F841
                else:
                    response.status_code = status.HTTP_404_NOT_FOUND
                    return StatusResponse(
                        message="Request can't be processed, please try again or contact admin."
                    )

            await session.commit()
            return StatusResponse(message="Request successful.")

    async def create_device_request(
        self,
        payload: MakeDeviceRequest,
        user: GetCurrentUser,
        session: DBSession,
        response: Response,
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

        # Fetch Admin; it's required for approval at any level
        admin_user = await session.scalar(
            select(User).where(User.role == UserRole.ADMIN)
        )
        if not admin_user:
            response.status_code = status.HTTP_404_NOT_FOUND
            return StatusResponse(message="Admin not found.")

        device_request = NewRepairDevicesRequest(
            requested_by=user.id,
            type=payload.type,
        )

        if payload.type == DeviceRequestType.NEW:
            device_request.requested_specs = payload.requested_specs
        else:
            device_request.device_id = payload.device_id

        cur_approver_email: str | None = None

        if user.role == UserRole.SUPERVISOR:
            device_request.pending_by = admin_user.id
            device_request.requested_specs = payload.requested_specs

            # Inform Admin through Email notification
            cur_approver_email = admin_user.email

            approvals = [RequestApproval(approver_id=admin_user.id, level=2)]

        elif user.role == UserRole.DEVELOPER and user.supervisor_assignment:
            # Fetch Developer's Supervisor id first to whom the request should be sent
            supervisor_id = user.supervisor_assignment.supervisor_id

            device_request.pending_by = supervisor_id
            device_request.device_id = payload.device_id

            # Intentionally, only to complete task quickly
            supervisor_email = await session.scalar(
                select(User.email).where(User.id == supervisor_id)
            )

            # Inform Supervisor through Email notification
            cur_approver_email = supervisor_email

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

        # Inform current level approval through Email notification
        print(f"sending email to {cur_approver_email}...")

        msg = "your supervisor" if user.role == UserRole.DEVELOPER else "the admin"
        return StatusResponse(message=f"Request has been sent to {msg} for approval.")

    # async def get_assigned_by_you_devices(
    #     self, user: GetCurrentUser, session: DBSession
    # ) -> list[AssignedByDevicesResponse]:
    #     result = await session.execute(
    #         select(DeviceAssignment)
    #         .options(selectinload(DeviceAssignment.assignments))
    #         .where(DeviceAssignment.assigned_by == user.id)
    #     )
    #     available_devices = result.all()
    #     return [
    #         AssignedByDevicesResponse(
    #             id=device.id,
    #             device_id=device.id,
    #             status_fullfilled=
    #         )
    #         for device in available_devices
    #     ]
