"""Sending one email through the host's mail server (LATTICE_SMTP_*).

Callers do not send directly: notifications queue emails in lattice.email and the
background sender calls send(). With no mail server configured, nothing is sent and the
queue keeps the email as logged, readable in Administration › Email.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from lattice.kernel.config import settings


class NotConfigured(Exception):
    """No mail server is set (LATTICE_SMTP_HOST is empty)."""


def send(to: str, subject: str, body: str) -> None:
    """Send a plain-text email. Raises NotConfigured, or the mail server's error."""
    if not settings.smtp_host:
        raise NotConfigured
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
