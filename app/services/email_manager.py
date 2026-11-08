import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "email"


settings = get_settings()


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

    async def send_transfer_otp(self, to_email: str, code: int):
        subject = f"[{code}] Confirm your e-mail address on {self.config.app_name}"

        template_path = TEMPLATE_DIR / "otp.html"
        body = template_path.read_text(encoding="utf-8")

        body = body.replace("{{APP_NAME}}", self.config.app_name)
        return await self._send(to_email, subject, body)
