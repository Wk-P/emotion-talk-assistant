import logging

import resend

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        # No API key configured yet — log instead of failing so the auth
        # flow is still testable end to end before Resend is wired up.
        logger.warning("RESEND_API_KEY not set; email not sent. to=%s subject=%s\n%s", to, subject, html)
        return

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.email_from,
            "to": to,
            "subject": subject,
            "html": html,
        }
    )
