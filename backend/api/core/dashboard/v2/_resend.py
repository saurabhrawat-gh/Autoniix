"""Resend transactional email module (Story #223).

Provides ``send_email(template_id, to, variables)`` — async fire-and-forget.
All 8 required templates are rendered inline here.

Environment variables:
    RESEND_API_KEY      - Required in production
    RESEND_FROM_EMAIL   - Defaults to "Autoniix <noreply@autoniix.com>"
    FRONTEND_URL        - Base URL for invite/reset links
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog

logger = structlog.get_logger()

_RESEND_API_URL = "https://api.resend.com/emails"


def is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY"))


def _from_email() -> str:
    return os.getenv("RESEND_FROM_EMAIL", "Autoniix <noreply@autoniix.com>")



def _wrap(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title></head>
<body style="font-family:sans-serif;color:#111;max-width:560px;margin:32px auto;padding:0 16px">
{body_html}
<hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb">
<p style="color:#6b7280;font-size:12px">Autoniix — automated YouTube content platform</p>
</body></html>"""


def _btn(url: str, label: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:10px 20px;'
        f'background:#10b981;color:#fff;text-decoration:none;border-radius:6px;'
        f'font-weight:600;margin:16px 0">{label}</a>'
    )



def _render(template_id: str, v: dict[str, Any]) -> tuple[str, str] | None:
    """Return (subject, html) or None if template_id unknown."""

    if template_id == "workspace-invite":
        invite_url = v.get("invite_url", "")
        expires_days = v.get("expires_days", 7)
        workspace_name = v.get("workspace_name", "a workspace")
        inviter_name = v.get("inviter_name", "Someone")
        inviter_email = v.get("inviter_email", "")
        role = v.get("role", "viewer")
        subject = f"{inviter_name} invited you to join {workspace_name} on Autoniix"
        html = _wrap(subject, f"""
<h2 style="margin-bottom:4px">{inviter_name} invited you to join <em>{workspace_name}</em></h2>
<p style="color:#6b7280;font-size:14px">{inviter_email}</p>
<p>You've been assigned the <strong>{role}</strong> role.</p>
{_btn(invite_url, "Accept Invitation")}
<p style="color:#6b7280;font-size:13px">This link expires in {expires_days} day{"s" if expires_days != 1 else ""}.</p>
<p style="color:#6b7280;font-size:13px">If you don't know {inviter_name}, you can safely ignore this email.</p>
""")
        return subject, html

    if template_id == "welcome-new-user":
        name = v.get("name") or v.get("email", "there")
        workspace_name = v.get("workspace_name", "your workspace")
        subject = f"Welcome to Autoniix, {name}!"
        html = _wrap(subject, f"""
<h2>Welcome to Autoniix, {name}! 🎉</h2>
<p>Your account has been created and you've joined <strong>{workspace_name}</strong>.</p>
<p>Start by connecting a YouTube channel and setting up your first content pipeline.</p>
""")
        return subject, html

    if template_id == "welcome-existing-user":
        name = v.get("name") or v.get("email", "there")
        workspace_name = v.get("workspace_name", "a workspace")
        role = v.get("role", "viewer")
        subject = f"You've joined {workspace_name}"
        html = _wrap(subject, f"""
<h2>You've joined <em>{workspace_name}</em></h2>
<p>Hi {name},</p>
<p>You now have <strong>{role}</strong> access to <strong>{workspace_name}</strong> on Autoniix.</p>
""")
        return subject, html

    if template_id == "ownership-transferred-new":
        name = v.get("name") or v.get("email", "there")
        workspace_name = v.get("workspace_name", "your workspace")
        subject = f"You are now the Owner of {workspace_name}"
        html = _wrap(subject, f"""
<h2>Ownership transferred to you</h2>
<p>Hi {name},</p>
<p>You are now the <strong>Owner</strong> of <strong>{workspace_name}</strong> on Autoniix.</p>
<p>As owner you have full administrative control over the workspace, billing, and members.</p>
""")
        return subject, html

    if template_id == "ownership-transferred-old":
        name = v.get("name") or v.get("email", "there")
        workspace_name = v.get("workspace_name", "your workspace")
        new_owner_name = v.get("new_owner_name", "another member")
        subject = f"Ownership of {workspace_name} has been transferred"
        html = _wrap(subject, f"""
<h2>Workspace ownership transferred</h2>
<p>Hi {name},</p>
<p>Ownership of <strong>{workspace_name}</strong> has been transferred to <strong>{new_owner_name}</strong>.</p>
<p>Your role has been changed to <strong>member</strong>. You still have access to all workspace content.</p>
<p style="color:#6b7280;font-size:13px">If you did not initiate this transfer, please contact support immediately.</p>
""")
        return subject, html

    if template_id == "member-removed":
        name = v.get("name") or v.get("email", "there")
        workspace_name = v.get("workspace_name", "a workspace")
        subject = f"You've been removed from {workspace_name}"
        html = _wrap(subject, f"""
<h2>Your access has been removed</h2>
<p>Hi {name},</p>
<p>You have been removed from <strong>{workspace_name}</strong> on Autoniix.</p>
<p style="color:#6b7280;font-size:13px">If you believe this is a mistake, contact the workspace admin.</p>
""")
        return subject, html

    if template_id == "forgot-password":
        email = v.get("email", "")
        reset_link = v.get("reset_link", "")
        subject = "Reset your Autoniix password"
        html = _wrap(subject, f"""
<h2>Reset your password</h2>
<p>We received a request to reset the password for <strong>{email}</strong>.</p>
{_btn(reset_link, "Reset password")}
<p style="word-break:break-all;color:#6b7280;font-size:13px">Or paste this link (expires in 1 hour):<br>
<a href="{reset_link}">{reset_link}</a></p>
<p style="color:#6b7280;font-size:13px">If you didn't request this, you can safely ignore this email — your password won't change.</p>
""")
        return subject, html

    if template_id == "password-changed":
        email = v.get("email", "")
        subject = "Your Autoniix password has been changed"
        html = _wrap(subject, f"""
<h2>Password changed</h2>
<p>The password for <strong>{email}</strong> was successfully changed.</p>
<p style="color:#6b7280;font-size:13px">If you did not make this change, please reset your password immediately or contact support.</p>
""")
        return subject, html

    return None



async def _send_now(template_id: str, to: str, variables: dict[str, Any]) -> bool:
    """Execute the HTTP call to Resend. Returns True on success."""
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("resend.not_configured", template=template_id, to=to)
        return False

    rendered = _render(template_id, variables)
    if rendered is None:
        logger.warning("resend.unknown_template", template=template_id)
        return False

    subject, html = rendered
    payload = {
        "from": _from_email(),
        "to": [to],
        "subject": subject,
        "html": html,
    }
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code in (200, 201):
            logger.info("resend.sent", template=template_id, to=to)
            return True
        logger.warning("resend.send_failed",
                       template=template_id, to=to,
                       status=resp.status_code, body=resp.text[:200])
        return False
    except Exception as exc:
        logger.warning("resend.send_error", template=template_id, to=to, error=str(exc))
        return False


def send_email(template_id: str, to: str, variables: dict[str, Any] | None = None) -> asyncio.Task:
    """Fire-and-forget transactional email send.

    Schedules the HTTP call as a background asyncio task so the API
    response is never blocked by email delivery.  The returned Task can
    be ignored by callers.
    """
    vars_ = variables or {}
    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(_send_now(template_id, to, vars_))
    except RuntimeError:
        return asyncio.ensure_future(_send_now(template_id, to, vars_))
