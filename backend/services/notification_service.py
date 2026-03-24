from __future__ import annotations

from email.message import EmailMessage
import smtplib
from typing import Iterable, List

from backend import posthog_tracker
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


def _is_email_configured() -> bool:
    return bool(config.SMTP_SERVER and config.SMTP_USERNAME and config.SMTP_PASSWORD)


def _send_email(subject: str, body: str, recipients: Iterable[str]) -> None:
    recipient_list: List[str] = [email.strip() for email in recipients if email and email.strip()]
    if not recipient_list:
        return
    if not _is_email_configured():
        raise RuntimeError("SMTP is not configured")

    from_email = config.EMAIL_FROM or config.SMTP_USERNAME
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(recipient_list)
    msg.set_content(body)

    with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.send_message(msg)


def notify_appointment_created(*, username: str, appointment_with: str, preferred_date: str, preferred_time: str, primary_reason: str, user_email: str) -> None:
    posthog_tracker.capture(
        distinct_id=username,
        event="appointment_requested",
        properties={
            "appointment_with": appointment_with,
            "preferred_date": preferred_date,
            "preferred_time": preferred_time,
            "primary_reason": primary_reason,
        },
    )

    admin_recipients = config.ADMIN_NOTIFICATION_EMAILS
    if admin_recipients:
        try:
            _send_email(
                subject="Smart AI Tutor appointment request",
                body=(
                    f"User: {username}\n"
                    f"Contact email: {user_email or 'Not provided'}\n"
                    f"Requested with: {appointment_with}\n"
                    f"Preferred date: {preferred_date}\n"
                    f"Preferred time: {preferred_time}\n"
                    f"Reason: {primary_reason}\n"
                ),
                recipients=admin_recipients,
            )
        except Exception as exc:
            logger.warning("Appointment admin notification failed: %s", exc)

    if user_email:
        try:
            _send_email(
                subject="We received your Smart AI Tutor appointment request",
                body=(
                    f"Hello {username},\n\n"
                    "Your appointment request has been recorded.\n"
                    f"Requested with: {appointment_with}\n"
                    f"Preferred date: {preferred_date}\n"
                    f"Preferred time: {preferred_time}\n"
                    f"Reason: {primary_reason}\n\n"
                    "We will follow up once it has been reviewed."
                ),
                recipients=[user_email],
            )
        except Exception as exc:
            logger.warning("Appointment confirmation email failed: %s", exc)


def notify_feedback_received(*, username: str, entry_type: str, category_or_feature: str, user_email: str) -> None:
    posthog_tracker.capture(
        distinct_id=username,
        event="support_intake_created",
        properties={
            "entry_type": entry_type,
            "category_or_feature": category_or_feature,
        },
    )

    admin_recipients = config.ADMIN_NOTIFICATION_EMAILS
    if not admin_recipients:
        return

    try:
        _send_email(
            subject=f"Smart AI Tutor {entry_type} submission",
            body=(
                f"User: {username}\n"
                f"Contact email: {user_email or 'Not provided'}\n"
                f"Type: {entry_type}\n"
                f"Category/feature: {category_or_feature or 'N/A'}\n"
            ),
            recipients=admin_recipients,
        )
    except Exception as exc:
        logger.warning("%s notification failed: %s", entry_type.capitalize(), exc)
