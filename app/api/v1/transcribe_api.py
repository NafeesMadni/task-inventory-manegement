import re
from datetime import UTC, datetime

from fastapi import APIRouter, UploadFile, status
from pydantic import ValidationError

from app.api.v1.types import (
    CeleryTranscribeResult,
    ProcessStartResponse,
    VoiceDeviceRecord,
)
from app.core.celery import celery_app
from app.dependencies import GetCurrentUser
from app.services.tasks_manager import process_transcript_with_ai, transcribe_audio


class TranscribeAPI:
    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/transcribe", tags=["Transcribe Audio Endpoint"]
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            "/init-process",
            endpoint=self.transcribe_and_prepare_payload,
            methods=["POST"],
            response_model=ProcessStartResponse,
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            "/task-status/{task_id}",
            endpoint=self.task_status,
            methods=["GET"],
            response_model=CeleryTranscribeResult,
            status_code=status.HTTP_200_OK,
        )

    async def transcribe_and_prepare_payload(
        self, file: UploadFile, _: GetCurrentUser
    ) -> ProcessStartResponse:
        workflow = (
            transcribe_audio.s(  # type: ignore
                audio_bytes=await file.read(),
                model_type="medium",
            )
            | process_transcript_with_ai.s(  # type: ignore
                recorded_on=datetime.now(UTC).strftime("%Y-%m-%d"),
                default_currency="PKR",
            )
        ).apply_async()

        return ProcessStartResponse(task_id=workflow.id)

    async def task_status(
        self, task_id: str, _: GetCurrentUser
    ) -> CeleryTranscribeResult:
        result = celery_app.AsyncResult(task_id)

        if result.failed():
            return CeleryTranscribeResult(
                task_id=task_id, status="Failed", developer_error=str(result.result)
            )

        if result.ready():
            output_text = result.result
            match = re.search(
                r"<device_record>(.*?)</device_record>", output_text, re.DOTALL
            )
            if not match:
                raise ValueError("No <device_record> block in the model's answer.")

            try:
                return CeleryTranscribeResult(
                    result=VoiceDeviceRecord.model_validate_json(match.group(1).strip())
                )
            except ValidationError as error:
                raise ValueError(
                    f"Model returned an invalid record: {error}"
                ) from error

        return CeleryTranscribeResult(task_id=task_id, status=result.status)
