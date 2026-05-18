"""Generic SMTP email helper for the dashboard service.

Single entry point :func:`send_email` reads SMTP config from environment
variables and delivers a multipart (HTML + plain-text) message via
``aiosmtplib``. The helper is intentionally minimal — no templating, no
queueing — because the only sender so far is the password-reset flow.

Environment variables (all optional except `SMTP_HOST` for a real send):
    SMTP_HOST           e.g. ``smtp.gmail.com`` / ``smtp.hostinger.com``
    SMTP_PORT           default ``587`` (STARTTLS) — use ``465`` for SMTPS
    SMTP_USER           username for SMTP AUTH (often the mailbox itself)
    SMTP_PASSWORD       SMTP password / app-password / API key
    SMTP_FROM           ``From:`` header (e.g. ``Autoniix <noreply@autoniix.com>``)
    SMTP_TLS            ``starttls`` (default) | ``ssl`` | ``none``
    SMTP_TIMEOUT_S      socket timeout in seconds (default ``10``)

If ``SMTP_HOST`` is unset the helper short-circuits and returns ``False``
without raising — callers should treat email delivery as best-effort.
"""
from __future__ import annotations

import logging
import os
from email.message import EmailMessage

log = logging.getLogger(__name__)


def is_configured() -> bool:
    """Return True iff a hostname is configured so we can attempt a send."""
    return bool(os.getenv("SMTP_HOST"))


def _build_message(to: str, subject: str, html: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "noreply@autoniix.com")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


async def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Send a multipart email. Returns ``True`` on success, ``False`` on
    failure or when SMTP is not configured. Never raises — callers receive
    a boolean and the failure (if any) is logged at WARNING."""
    if not is_configured():
        log.info("SMTP not configured; skipping email to %s (subject=%r)", to, subject)
        return False

    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER") or None
    password = os.getenv("SMTP_PASSWORD") or None
    tls_mode = os.getenv("SMTP_TLS", "starttls").lower()
    timeout = float(os.getenv("SMTP_TIMEOUT_S", "10"))

    msg = _build_message(to=to, subject=subject, html=html, text=text)

    try:
        # Import lazily so the module loads cleanly even if the dependency
        # is missing in environments that never send mail (e.g. CI).
        import aiosmtplib  # type: ignore

        use_tls = tls_mode == "ssl"
        start_tls = tls_mode == "starttls"
        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            username=user,
            password=password,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=timeout,
        )
        log.info("email sent to=%s subject=%r host=%s", to, subject, host)
        return True
    except Exception as exc:  # pragma: no cover - best-effort delivery
        # Never log credentials. ``exc`` from aiosmtplib does not include them.
        log.warning("email send failed to=%s subject=%r err=%s", to, subject, exc)
        return False
