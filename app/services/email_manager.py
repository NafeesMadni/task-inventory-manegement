import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from fastapi.concurrency import run_in_threadpool
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings
from app.database.models import DeviceRequestType

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"

settings = get_settings()

SCHEDULE_MESSAGES = {
    DeviceRequestType.NEW: {
        "title": "New Device Handover Scheduled",
        "message": "Your new device request has been approved. "
        "The device handover is scheduled for:",
        "action": "Device Handover",
    },
    DeviceRequestType.EXISTING: {
        "title": "Existing Device Handover Scheduled",
        "message": "Your requested device is scheduled for collection or handover on:",
        "action": "Device Handover",
    },
    DeviceRequestType.REPAIR: {
        "title": "Device Repair Scheduled",
        "message": "The repair of your device is scheduled for:",
        "action": "Device Repair",
    },
}


@dataclass
class SMTPConfig:
    app_name: str
    user: str
    host: str
    port: int
    password: str


class EmailManager:
    def __init__(self) -> None:
        self.config = SMTPConfig(
            app_name=settings.APP_NAME,
            user=settings.GMAIL_USER,
            host=settings.GMAIL_HOST,
            port=settings.GMAIL_PORT,
            password=settings.GMAIL_PASSWORD,
        )

        self.template_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def _send(self, to_email: str, subject: str, body: str):
        """Private helper to handle SMTP connection and delivery."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.user
        msg["To"] = to_email

        msg.attach(MIMEText(body, "html", "utf-8"))

        def _sync_send():
            with smtplib.SMTP(self.config.host, self.config.port) as server:
                server.starttls()
                server.login(self.config.user, self.config.password)
                server.send_message(msg)

        await run_in_threadpool(_sync_send)

    async def send_join_request_decision(
        self,
        to_email: str,
        requested_role: str,
        approved: bool,
        approver_username: str,
        approver_role: str,
        processed_reason: str | None = None,
        processed_at: datetime | None = None,
    ) -> None:
        """Send join request approval/rejection notification."""

        template = self.template_env.get_template("join_request_decision.html")

        formatted_processed_at = (
            processed_at.strftime("%d %B %Y, %I:%M %p") if processed_at else None
        )

        context = {
            "app_name": self.config.app_name,
            "requested_role": requested_role,
            "approved": approved,
            "approver_username": approver_username,
            "approver_role": approver_role,
            "processed_reason": processed_reason,
            "processed_at": formatted_processed_at,
        }

        body = template.render(**context)

        decision = "Approved" if approved else "Rejected"

        subject = f"{self.config.app_name} - Join Request {decision}"

        await self._send(to_email, subject, body)

    async def send_join_request_notification(
        self,
        to_email: str,
        approver_username: str,
        requester_username: str,
        requester_name: str,
        requester_email: str,
        requested_role: str,
        requested_at: datetime,
    ) -> None:
        """Notify approver about a new join request."""

        template = self.template_env.get_template("join_request_notification.html")

        context = {
            "app_name": self.config.app_name,
            "approver_username": approver_username,
            "requester_username": requester_username,
            "requester_name": requester_name,
            "requester_email": requester_email,
            "requested_role": requested_role,
            "requested_at": requested_at.strftime("%d %B %Y, %I:%M %p"),
        }

        body = template.render(**context)

        subject = f"{self.config.app_name} - New Join Request"

        await self._send(to_email, subject, body)

    async def send_device_request_notification(
        self,
        to_email: str,
        approver_username: str,
        requester_username: str,
        requester_name: str,
        request_id: int,
        request_type: str,
        requested_at: datetime,
        device_name: str | None = None,
        device_serial: str | None = None,
        requested_specs: str | None = None,
    ) -> None:
        """Notify current approver about a device request (NEW/EXISTING/REAPIR)."""

        template = self.template_env.get_template("device_request_notification.html")

        context = {
            "app_name": self.config.app_name,
            "approver_username": approver_username,
            "requester_username": requester_username,
            "requester_name": requester_name,
            "request_id": request_id,
            "request_type": request_type.replace("_", " ").title(),
            "requested_at": requested_at.strftime("%d %B %Y, %I:%M %p"),
            "device_name": device_name,
            "device_serial": device_serial,
            "requested_specs": requested_specs if requested_specs else None,
        }

        body = template.render(**context)

        subject = (
            f"{self.config.app_name} - "
            f"New {request_type.replace('_', ' ').title()} Request #{request_id}"
        )

        await self._send(to_email, subject, body)

    async def send_device_request_decision(
        self,
        to_email: str,
        request_id: int,
        device_name: str,
        approved: bool,
        approver_username: str,
        approver_role: str,
        remarks: str | None = None,
        next_approver_username: str | None = None,
        next_approver_role: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> None:
        """Send device request approval/rejection notification to a requester."""

        template = self.template_env.get_template("device_request_decision.html")

        formatted_scheduled_at = (
            scheduled_at.strftime("%d %B %Y, %I:%M %p") if scheduled_at else None
        )

        context = {
            "app_name": self.config.app_name,
            "request_id": request_id,
            "device_name": device_name,
            "approved": approved,
            "approver_username": approver_username,
            "approver_role": approver_role,
            "remarks": remarks,
            "next_approver_username": next_approver_username,
            "next_approver_role": next_approver_role,
            "scheduled_at": formatted_scheduled_at,
        }

        body = template.render(**context)

        decision = "Approved" if approved else "Rejected"

        subject = f"{self.config.app_name} - Device Request #{request_id} {decision}"

        await self._send(to_email, subject, body)

    async def send_device_scheduled_reminder(
        self,
        to_email: str,
        requester_username: str,
        request_id: int,
        request_type: DeviceRequestType,
        device_name: str,
        device_serial: str,
        scheduled_at: datetime,
    ) -> None:
        """Notify requester when their device schedule arrives."""

        template = self.template_env.get_template("device_scheduled_reminder.html")

        schedule_info = SCHEDULE_MESSAGES[request_type]

        context = {
            "app_name": self.config.app_name,
            "requester_username": requester_username,
            "request_id": request_id,
            "title": schedule_info["title"],
            "message": schedule_info["message"],
            "action": schedule_info["action"],
            "device_name": device_name,
            "device_serial": device_serial,
            "scheduled_at": scheduled_at.strftime("%d %B %Y, %I:%M %p"),
        }

        body = template.render(**context)

        subject = f"{self.config.app_name} - Device Schedule Reminder #{request_id}"

        await self._send(to_email, subject, body)

    async def send_device_request_fulfilled(
        self,
        to_email: str,
        requester_username: str,
        request_id: int,
        request_type: DeviceRequestType,
        device_name: str,
        device_serial: str | None,
        processed_at: datetime,
    ) -> None:

        messages = {
            DeviceRequestType.NEW: (
                "New Device Request Fulfilled",
                "Your new device handover has been recorded successfully.",
            ),
            DeviceRequestType.EXISTING: (
                "Device Assignment Completed",
                "Your requested device has been assigned successfully.",
            ),
            DeviceRequestType.REPAIR: (
                "Device Repair Completed",
                "Your device repair has been marked as completed.",
            ),
        }

        title, message = messages[request_type]

        template = self.template_env.get_template("device_request_fulfilled.html")

        body = template.render(
            app_name=self.config.app_name,
            title=title,
            message=message,
            requester_username=requester_username,
            request_id=request_id,
            device_name=device_name,
            device_serial=device_serial,
            processed_at=processed_at.strftime("%d %B %Y, %I:%M %p"),
        )

        subject = f"{self.config.app_name} - {title} #{request_id}"

        await self._send(to_email, subject, body)
