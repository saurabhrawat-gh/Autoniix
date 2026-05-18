"""Real auth — Phase 4 (S7).

Endpoints:
  POST /auth/register
  POST /auth/login
  POST /auth/refresh
  POST /auth/logout
  GET  /auth/me
  POST /auth/forgot
  POST /auth/reset
  POST /auth/mfa/setup
  POST /auth/mfa/verify

Single-tenant scope: the first user that registers gets ``role='owner'``;
subsequent users default to ``viewer`` and need an Owner to promote them.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from src.db import get_pool
from src.services.dashboard._limiter import limiter

from ._deps import Principal, audit, principal_dep

router = APIRouter()


_INSECURE_JWT_DEFAULTS = frozenset({
    "dev-insecure-change-me",
    "change_me_to_64_char_random_string_here_now",
    "",
})


def _jwt_secret() -> str:
    secret = (
        os.getenv("AUTH_JWT_SECRET")
        or os.getenv("DASHBOARD_JWT_SECRET")
        or "dev-insecure-change-me"
    )
    if secret in _INSECURE_JWT_DEFAULTS and os.getenv("ENVIRONMENT_MODE", "test").lower() == "production":
        raise RuntimeError(
            "AUTH_JWT_SECRET is the insecure default. "
            "Generate a real secret: openssl rand -base64 48 "
            "and set it as AUTH_JWT_SECRET in your .env before running in production."
        )
    return secret


def _hash_pw(pw: str) -> str:
    try:
        from argon2 import PasswordHasher
        return PasswordHasher().hash(pw)
    except Exception:
        # Fallback (still salted, but weaker). Argon2 is the soft requirement.
        salt = secrets.token_hex(16)
        return "pbkdf2$" + salt + "$" + hashlib.pbkdf2_hmac(
            "sha256", pw.encode(), salt.encode(), 200_000
        ).hex()


def _verify_pw(pw: str, hashed: str) -> bool:
    try:
        if hashed.startswith("pbkdf2$"):
            _, salt, digest = hashed.split("$", 2)
            calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
            return secrets.compare_digest(calc, digest)
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        try:
            PasswordHasher().verify(hashed, pw)
            return True
        except VerifyMismatchError:
            return False
    except Exception:
        return False


def _issue_jwt(user: dict[str, Any], workspace_id: int = 1, ws_role: str | None = None, ttl_s: int = 3600) -> str:
    import jwt
    return jwt.encode(
        {
            "sub": str(user["id"]),
            "email": user["email"],
            "role": ws_role or user.get("role", "viewer"),
            "wid": workspace_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + ttl_s,
        },
        _jwt_secret(),
        algorithm="HS256",
    )


def _refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _cookie_secure() -> bool:
    return os.getenv("ENVIRONMENT_MODE", "test").lower() == "production"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        key="access_token", value=access,
        httponly=True, secure=secure, samesite="lax",
        max_age=3600, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh,
        httponly=True, secure=secure, samesite="lax",
        max_age=2592000, path="/api/v2/auth/refresh",
    )
    response.set_cookie(
        key="auth_status", value="1",
        httponly=False, secure=secure, samesite="lax",
        max_age=3600, path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v2/auth/refresh")
    response.delete_cookie("auth_status", path="/")


# Schemas
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8)


class MfaVerifyIn(BaseModel):
    code: str


class ProfileIn(BaseModel):
    display_name: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8)


# Endpoints
@router.get("/mode")
async def auth_mode():
    """Public — no auth required. Returns which auth backends are active.

    The login UI calls this on mount to decide which form to render.
    Returns both flags so the UI can handle a partial migration window.
    """
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT key, enabled FROM feature_flags WHERE key IN ('auth.v2.enabled','auth.legacy.enabled')"
        )
        flags = {r["key"]: r["enabled"] for r in rows}
    except Exception:
        flags = {}
    return {
        "v2_enabled": flags.get("auth.v2.enabled", True),
        "legacy_enabled": flags.get("auth.legacy.enabled", False),
    }


@router.post("/register")
async def register(body: RegisterIn, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE lower(email)=lower($1)", body.email
        )
        if existing:
            raise HTTPException(409, "Email already registered")
        verify_token = secrets.token_urlsafe(32)
        uid = await conn.fetchval(
            """INSERT INTO users (email, display_name, password_hash, role,
                                  email_verify_token, email_verified)
               VALUES ($1,$2,$3,$4,$5,TRUE) RETURNING id""",
            body.email.lower(), body.display_name, _hash_pw(body.password),
            "owner", verify_token,
        )
        # Each registration creates a fresh workspace owned by this user
        ws_name = (body.display_name or body.email.split("@")[0]).title() + "'s Workspace"
        ws_slug = body.email.split("@")[0].lower().replace(".", "-")[:60]
        # Make slug unique if colliding
        suffix = 0
        while await conn.fetchval("SELECT id FROM workspaces WHERE slug=$1", ws_slug if suffix == 0 else f"{ws_slug}-{suffix}"):
            suffix += 1
        if suffix:
            ws_slug = f"{ws_slug}-{suffix}"
        ws_id = await conn.fetchval(
            """INSERT INTO workspaces (name, slug, plan, owner_user_id, billing_email)
               VALUES ($1,$2,'starter',$3,$4) RETURNING id""",
            ws_name, ws_slug, uid, body.email.lower(),
        )
        # Add to workspace_members as owner
        await conn.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES ($1,$2,'owner')",
            ws_id, uid,
        )
        # Set active workspace
        await conn.execute(
            "UPDATE users SET active_workspace_id=$1 WHERE id=$2", ws_id, uid
        )
    return {"status": "ok", "user_id": uid, "workspace_id": ws_id, "role": "owner"}


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginIn, response: Response):
    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id, email, password_hash, role, mfa_secret, mfa_enabled, disabled "
        "FROM users WHERE lower(email)=lower($1)",
        body.email,
    )
    if not user or user["disabled"]:
        raise HTTPException(401, "Invalid credentials")
    if not _verify_pw(body.password, user["password_hash"] or ""):
        raise HTTPException(401, "Invalid credentials")
    if user["mfa_enabled"]:
        if not body.mfa_code:
            raise HTTPException(401, "MFA required")
        try:
            import pyotp
            if not pyotp.TOTP(user["mfa_secret"]).verify(body.mfa_code, valid_window=1):
                raise HTTPException(401, "Invalid MFA code")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(500, "MFA verification unavailable")
    raw, hashed = _refresh_token()
    expires = datetime.utcnow() + timedelta(days=30)
    await pool.execute(
        """INSERT INTO sessions (user_id, refresh_token_hash, ip, user_agent, expires_at)
           VALUES ($1,$2,$3,$4,$5)""",
        user["id"], hashed,
        (request.client.host if request.client else None),
        request.headers.get("user-agent"), expires,
    )
    await pool.execute("UPDATE users SET last_login_at=NOW() WHERE id=$1", user["id"])
    # Resolve active workspace + workspace-scoped role
    ws_row = await pool.fetchrow(
        "SELECT active_workspace_id FROM users WHERE id=$1", user["id"]
    )
    wid = (ws_row["active_workspace_id"] if ws_row else None) or 1
    wm = await pool.fetchrow(
        "SELECT role FROM workspace_members WHERE workspace_id=$1 AND user_id=$2", wid, user["id"]
    )
    ws_role = wm["role"] if wm else user["role"]
    access = _issue_jwt(dict(user), workspace_id=wid, ws_role=ws_role)
    _set_auth_cookies(response, access, raw)
    # Also return token in body as a fallback for environments where the dev
    # proxy (e.g. `next dev` rewrites) does not forward Set-Cookie reliably.
    # The frontend persists it in localStorage and sends as Authorization: Bearer.
    return {
        "status": "ok",
        "user": {"id": user["id"], "email": user["email"], "role": ws_role, "workspace_id": wid},
        "access_token": access,
        "expires_in": 3600,
    }


@router.post("/refresh")
async def refresh(request: Request, response: Response, body: RefreshIn | None = None):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token and body:
        raw_token = body.refresh_token
    if not raw_token:
        raise HTTPException(401, "Missing refresh token")
    h = hashlib.sha256(raw_token.encode()).hexdigest()
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT s.id, s.user_id, s.expires_at, s.revoked_at, s.rotated_at,
                  u.email, u.role, u.disabled
             FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.refresh_token_hash=$1""",
        h,
    )
    if (not row or row["revoked_at"] is not None or row["rotated_at"] is not None
            or row["expires_at"] < datetime.utcnow() or row["disabled"]):
        raise HTTPException(401, "Invalid refresh token")
    new_raw, new_hashed = _refresh_token()
    new_expires = datetime.utcnow() + timedelta(days=30)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE sessions SET rotated_at=NOW() WHERE id=$1", row["id"])
            await conn.execute(
                """INSERT INTO sessions (user_id, refresh_token_hash, expires_at)
                   VALUES ($1,$2,$3)""",
                row["user_id"], new_hashed, new_expires,
            )
    ws_row = await pool.fetchrow(
        "SELECT active_workspace_id FROM users WHERE id=$1", row["user_id"]
    )
    wid = (ws_row["active_workspace_id"] if ws_row else None) or 1
    wm = await pool.fetchrow(
        "SELECT role FROM workspace_members WHERE workspace_id=$1 AND user_id=$2", wid, row["user_id"]
    )
    ws_role = wm["role"] if wm else row["role"]
    access = _issue_jwt(
        {"id": row["user_id"], "email": row["email"], "role": ws_role},
        workspace_id=wid, ws_role=ws_role,
    )
    _set_auth_cookies(response, access, new_raw)
    return {"status": "ok", "access_token": access, "expires_in": 3600}


@router.post("/logout")
async def logout(request: Request, response: Response, body: RefreshIn | None = None, _: Principal = Depends(principal_dep)):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token and body:
        raw_token = body.refresh_token
    if raw_token:
        h = hashlib.sha256(raw_token.encode()).hexdigest()
        pool = await get_pool()
        await pool.execute(
            "UPDATE sessions SET revoked_at=NOW() WHERE refresh_token_hash=$1", h
        )
    _clear_auth_cookies(response)
    return {"status": "ok"}


@router.get("/me")
async def me(p: Principal = Depends(principal_dep)):
    display_name = None
    if p.user_id:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT display_name FROM users WHERE id=$1", p.user_id)
        if row:
            display_name = row["display_name"]
    initials = ''
    if display_name:
        parts = display_name.strip().split()
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper()
    elif p.email:
        initials = p.email[0].upper()
    return {"data": {
        "user_id": p.user_id,
        "email": p.email,
        "role": p.role,
        "source": p.source,
        "display_name": display_name,
        "initials": initials,
    }}


@router.put("/profile")
async def update_profile(body: ProfileIn, p: Principal = Depends(principal_dep)):
    if not p.user_id:
        raise HTTPException(403, "Cannot update profile on a legacy session — enable v2 auth first")
    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id, password_hash FROM users WHERE id=$1", p.user_id
    )
    if not user:
        raise HTTPException(404, "User not found")

    updates: list[str] = []
    params: list = []

    if body.display_name is not None:
        params.append(body.display_name)
        updates.append(f"display_name=${len(params)}")

    if body.new_password is not None:
        if not body.current_password:
            raise HTTPException(400, "current_password is required to change your password")
        if not _verify_pw(body.current_password, user["password_hash"] or ""):
            raise HTTPException(401, "Current password is incorrect")
        params.append(_hash_pw(body.new_password))
        updates.append(f"password_hash=${len(params)}")
        # Revoke all other sessions when password changes
        await pool.execute(
            "UPDATE sessions SET revoked_at=NOW() WHERE user_id=$1 AND revoked_at IS NULL",
            p.user_id,
        )

    if not updates:
        raise HTTPException(400, "Nothing to update — provide display_name or new_password")

    params.append(p.user_id)
    await pool.execute(
        f"UPDATE users SET updated_at=NOW(), {', '.join(updates)} WHERE id=${len(params)}",
        *params,
    )
    return {"status": "ok", "message": "Profile updated"}


@router.post("/forgot")
async def forgot(body: ForgotIn):
    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id FROM users WHERE lower(email)=lower($1)", body.email
    )
    if not user:
        return {"status": "ok"}  # Do not leak existence
    raw = secrets.token_urlsafe(32)
    h = hashlib.sha256(raw.encode()).hexdigest()
    await pool.execute(
        """INSERT INTO password_resets (user_id, token_hash, expires_at)
           VALUES ($1,$2,NOW() + INTERVAL '1 hour')""",
        user["id"], h,
    )
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    reset_link = f"{frontend_url}/reset-password?token={raw}"
    if webhook_url:
        try:
            import httpx
            msg = f"Password reset requested for {body.email}. Link: {reset_link} (expires in 1 hour)."
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json={"text": msg}, timeout=5.0)
        except Exception:
            pass
    is_prod = os.getenv("ENVIRONMENT_MODE", "test").lower() == "production"
    return {"status": "ok"} if is_prod else {"status": "ok", "reset_token": raw}


@router.post("/reset")
async def reset(body: ResetIn):
    h = hashlib.sha256(body.token.encode()).hexdigest()
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, user_id, expires_at, used_at FROM password_resets WHERE token_hash=$1",
        h,
    )
    if not row or row["used_at"] or row["expires_at"] < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired token")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET password_hash=$1 WHERE id=$2",
                _hash_pw(body.password), row["user_id"],
            )
            await conn.execute(
                "UPDATE password_resets SET used_at=NOW() WHERE id=$1", row["id"]
            )
            await conn.execute(
                "UPDATE sessions SET revoked_at=NOW() WHERE user_id=$1 AND revoked_at IS NULL",
                row["user_id"],
            )
    return {"status": "ok"}


# Multi-workspace endpoints

class SwitchWorkspaceIn(BaseModel):
    workspace_id: int


class AcceptInviteIn(BaseModel):
    token: str
    password: str | None = Field(default=None, min_length=8)  # required for new accounts
    display_name: str | None = None


@router.get("/workspaces")
async def list_workspaces(p: Principal = Depends(principal_dep)):
    """Return all workspaces the current user is a member of."""
    if not p.user_id:
        return {"data": [{"id": 1, "name": "Default Workspace", "slug": "default",
                          "plan": "starter", "role": "owner", "active": True}]}
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT w.id, w.name, w.slug, w.plan, wm.role,
                  (w.id = u.active_workspace_id) AS active
             FROM workspace_members wm
             JOIN workspaces w ON w.id = wm.workspace_id
             JOIN users u      ON u.id = wm.user_id
            WHERE wm.user_id = $1
            ORDER BY w.name""",
        p.user_id,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/switch-workspace")
async def switch_workspace(body: SwitchWorkspaceIn, response: Response, p: Principal = Depends(principal_dep)):
    """Switch the current user's active workspace and return a new JWT pair."""
    if not p.user_id:
        raise HTTPException(403, "Cannot switch workspace on a legacy session")
    pool = await get_pool()
    member = await pool.fetchrow(
        "SELECT role FROM workspace_members WHERE workspace_id=$1 AND user_id=$2",
        body.workspace_id, p.user_id,
    )
    if not member:
        raise HTTPException(403, "Not a member of that workspace")
    user = await pool.fetchrow(
        "SELECT id, email, role, mfa_enabled, disabled FROM users WHERE id=$1", p.user_id
    )
    if not user or user["disabled"]:
        raise HTTPException(403, "User disabled")
    # Persist new active workspace
    await pool.execute(
        "UPDATE users SET active_workspace_id=$1 WHERE id=$2", body.workspace_id, p.user_id
    )
    # Issue fresh token pair
    raw, hashed = _refresh_token()
    expires = datetime.utcnow() + timedelta(days=30)
    await pool.execute(
        """INSERT INTO sessions (user_id, refresh_token_hash, expires_at)
           VALUES ($1,$2,$3)""",
        p.user_id, hashed, expires,
    )
    access = _issue_jwt(dict(user), workspace_id=body.workspace_id, ws_role=member["role"])
    _set_auth_cookies(response, access, raw)
    return {"status": "ok", "workspace_id": body.workspace_id, "role": member["role"]}


@router.get("/invite-info")
async def invite_info(token: str):
    """Public — no auth needed. Returns invite metadata so the UI can show the right form."""
    h = hashlib.sha256(token.encode()).hexdigest()
    pool = await get_pool()
    invite = await pool.fetchrow(
        "SELECT email, role, workspace_id, accepted_at, expires_at FROM workspace_invitations WHERE token_hash=$1",
        h,
    )
    if not invite:
        raise HTTPException(400, "Invalid invitation token")
    if invite["accepted_at"] is not None:
        raise HTTPException(400, "Invitation already used")
    if invite["expires_at"] < datetime.utcnow():
        raise HTTPException(400, "Invitation has expired")
    user_exists = bool(await pool.fetchval(
        "SELECT id FROM users WHERE lower(email)=lower($1)", invite["email"]
    ))
    ws = await pool.fetchrow("SELECT name FROM workspaces WHERE id=$1", invite["workspace_id"])
    return {
        "email": invite["email"],
        "role": invite["role"],
        "workspace_name": ws["name"] if ws else "Unknown workspace",
        "user_exists": user_exists,
    }


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteIn, request: Request, response: Response):
    """Accept a workspace invitation. Creates account if needed."""
    h = hashlib.sha256(body.token.encode()).hexdigest()
    pool = await get_pool()
    invite = await pool.fetchrow(
        """SELECT id, workspace_id, email, role, accepted_at, expires_at
             FROM workspace_invitations WHERE token_hash=$1""",
        h,
    )
    if not invite:
        raise HTTPException(400, "Invalid invitation token")
    if invite["accepted_at"] is not None:
        raise HTTPException(400, "Invitation already used")
    if invite["expires_at"] < datetime.utcnow():
        raise HTTPException(400, "Invitation has expired")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Find or create the user
            user = await conn.fetchrow(
                "SELECT id, email, role, disabled FROM users WHERE lower(email)=lower($1)",
                invite["email"],
            )
            if user:
                uid = user["id"]
                if user["disabled"]:
                    raise HTTPException(403, "Account is disabled")
            else:
                if not body.password:
                    raise HTTPException(400, "password is required for new accounts")
                uid = await conn.fetchval(
                    """INSERT INTO users (email, display_name, password_hash, role,
                                          email_verified, active_workspace_id)
                       VALUES ($1,$2,$3,'viewer',TRUE,$4) RETURNING id""",
                    invite["email"].lower(), body.display_name,
                    _hash_pw(body.password), invite["workspace_id"],
                )
            # Add to workspace_members (upsert)
            await conn.execute(
                """INSERT INTO workspace_members (workspace_id, user_id, role, invited_by)
                   VALUES ($1,$2,$3,NULL)
                   ON CONFLICT (workspace_id, user_id) DO UPDATE SET role=EXCLUDED.role""",
                invite["workspace_id"], uid, invite["role"],
            )
            # Set active workspace
            await conn.execute(
                "UPDATE users SET active_workspace_id=$1 WHERE id=$2",
                invite["workspace_id"], uid,
            )
            # Mark invite accepted
            await conn.execute(
                "UPDATE workspace_invitations SET accepted_at=NOW() WHERE id=$1", invite["id"]
            )

    # Issue tokens
    user_row = await pool.fetchrow(
        "SELECT id, email, role FROM users WHERE id=$1", uid
    )
    raw, hashed = _refresh_token()
    expires = datetime.utcnow() + timedelta(days=30)
    await pool.execute(
        """INSERT INTO sessions (user_id, refresh_token_hash, ip, user_agent, expires_at)
           VALUES ($1,$2,$3,$4,$5)""",
        uid, hashed,
        (request.client.host if request.client else None),
        request.headers.get("user-agent"), expires,
    )
    access = _issue_jwt(dict(user_row), workspace_id=invite["workspace_id"], ws_role=invite["role"])
    _set_auth_cookies(response, access, raw)
    return {"status": "ok", "workspace_id": invite["workspace_id"], "role": invite["role"]}


@router.post("/mfa/setup")
async def mfa_setup(p: Principal = Depends(principal_dep)):
    if not p.user_id:
        raise HTTPException(403, "Cannot enable MFA on legacy session")
    try:
        import pyotp
    except Exception:
        raise HTTPException(500, "MFA library unavailable")
    secret = pyotp.random_base32()
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET mfa_secret=$1 WHERE id=$2", secret, p.user_id
    )
    issuer = "yt-automation"
    uri = pyotp.TOTP(secret).provisioning_uri(name=p.email or "user", issuer_name=issuer)
    return {"data": {"otpauth_url": uri, "secret": secret}}


@router.post("/mfa/verify")
async def mfa_verify(body: MfaVerifyIn, p: Principal = Depends(principal_dep)):
    if not p.user_id:
        raise HTTPException(403, "No user context")
    pool = await get_pool()
    row = await pool.fetchrow("SELECT mfa_secret FROM users WHERE id=$1", p.user_id)
    if not row or not row["mfa_secret"]:
        raise HTTPException(400, "MFA not initialized")
    try:
        import pyotp
        if not pyotp.TOTP(row["mfa_secret"]).verify(body.code, valid_window=1):
            raise HTTPException(401, "Invalid code")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, "MFA library unavailable")
    await pool.execute("UPDATE users SET mfa_enabled=TRUE WHERE id=$1", p.user_id)
    return {"status": "ok"}
