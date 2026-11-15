import asyncio
import tempfile
from datetime import UTC, datetime
from typing import get_args, get_origin

import whisper
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery import celery_app
from app.database.db import get_sessionmaker
from app.database.models import DevicesRequest
from app.database.models.device import Device
from app.database.models.device_assignment import DeviceAssignment
from app.database.models.device_repair import DeviceRepair
from app.database.models.enums import (
    DeviceCondition,
    DeviceRequestStatus,
    DeviceRequestType,
    DeviceStatus,
    RepairStatus,
)
from app.services import EmailManager


@celery_app.task(name="send_device_scheduled_reminder_alert", max_retries=3)
def send_device_scheduled_reminder_alert(**kwargs):
    asyncio.run(EmailManager().send_device_scheduled_reminder(**kwargs))
    return "Device scheduled notification alert has been sent to the requester."


@celery_app.task(name="process_scheduled_device_request", max_retries=3)
def process_scheduled_device_request(request_id: int) -> str:
    return asyncio.run(_process_request(request_id))


async def _process_request(request_id: int) -> str:
    LocalSession = await get_sessionmaker()

    async with LocalSession() as session:
        request_record = await session.scalar(
            select(DevicesRequest)
            .options(
                selectinload(DevicesRequest.device),
                selectinload(DevicesRequest.requester),
            )
            .where(DevicesRequest.id == request_id)
        )

        if not request_record:
            return "Request not found, Request ID: {request_id}."

        device = request_record.device

        if not device:
            return f"Device againts this request not found!, Request ID: {request_id}."

        if request_record.status == DeviceRequestStatus.FULFILLED:
            return "Request has already been approved and fulfilled."
        elif request_record.status != DeviceRequestStatus.APPROVED:
            return "Request has not been approved by admin yet."
        else:
            # Only process the approved requests
            if request_record.type == DeviceRequestType.REPAIR:
                device_repair_record = await session.scalar(
                    select(DeviceRepair)
                    .options(
                        selectinload(DeviceRepair.device).selectinload(Device.repairs)
                    )
                    .where(
                        DeviceRepair.request_id == request_id,
                        DeviceRepair.status == RepairStatus.SCHEDULED,
                    )
                )
                if device_repair_record:
                    device.status = DeviceStatus.ASSIGNED

                    # Find device total repairs
                    repair_count = len(device.repairs)

                    if repair_count == 0:
                        device.condition = DeviceCondition.NEW
                    elif repair_count == 1:
                        device.condition = DeviceCondition.GOOD
                    elif 2 <= repair_count <= 3:
                        device.condition = DeviceCondition.FAIR
                    else:
                        device.condition = DeviceCondition.POOR

                    device_repair_record.status = RepairStatus.COMPLETED

            elif (
                request_record.type == DeviceRequestType.EXISTING
                or request_record.type == DeviceRequestType.NEW
            ):
                device_assignment_record = await session.scalar(
                    select(DeviceAssignment)
                    .options(selectinload(DeviceAssignment.device))
                    .where(
                        DeviceAssignment.request_id == request_id,
                        DeviceAssignment.assigned_at.is_(None),
                    )
                )
                if device_assignment_record:
                    device.status = DeviceStatus.ASSIGNED

                    device_assignment_record.condition_on_issue = device.condition
                    device_assignment_record.assigned_at = datetime.now(UTC)

        notification_data = None

        request_record.status = DeviceRequestStatus.FULFILLED

        notification_data = {
            "to_email": request_record.requester.email,
            "requester_username": request_record.requester.username,
            "request_id": request_id,
            "request_type": request_record.type,
            "device_name": device.name,
            "device_serial": device.serial_no,
            "processed_at": datetime.now(UTC),
        }
        await session.commit()

        await EmailManager().send_device_request_fulfilled(**notification_data)

    return "Request hasn been fulfilled."


@celery_app.task(name="transcribe_audio")
def trnascribe_audio(audio_bytes: bytes, model_type: str = "medium"):

    with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
        temp_file.write(audio_bytes)
        temp_file.flush()

        audio = whisper.load_audio(temp_file.name)

    model = whisper.load_model(model_type)
    result = model.transcribe(audio)
    return result["text"]


def model_to_string(model: type[BaseModel], indent: int = 0) -> str:
    lines = []

    for name, field in model.model_fields.items():
        annotation = field.annotation
        prefix = " " * indent

        lines.append(f"{prefix}{name}: {annotation}")

        origin = get_origin(annotation)  # noqa: F841
        args = get_args(annotation)

        # Handle nested Pydantic models
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            lines.append(model_to_string(annotation, indent + 4))

        # Handle List[SomeModel], Optional[SomeModel], etc.
        elif args:
            for arg in args:
                if isinstance(arg, type) and issubclass(arg, BaseModel):
                    lines.append(model_to_string(arg, indent + 4))

    return "\n".join(lines)
