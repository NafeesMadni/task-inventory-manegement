import asyncio

from app.core.celery import celery_app
from app.services import EmailManager


@celery_app.task(name="send_device_scheduled_reminder_alert")
def send_device_scheduled_reminder_alert(**kwrgs):
    asyncio.run(EmailManager().send_device_scheduled_reminder(**kwrgs))
    return "Device scheduled notification alert has been sent to the requester."
