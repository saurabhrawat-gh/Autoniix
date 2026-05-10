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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from src.db import get_pool

from ._deps import Principal, audit, principal_dep

router = APIRouter()


def _jwt_secret() -> str:
    return os.getenv("AUTH_JWT_SECRET") or os.getenv("DASHBOARD_JWT_SECRET") or "dev-insecure-change-me"


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


def _issue_jwt(user: dict[str, Any], ttl_s: int = 3600) -> str:
    import jwt
    return jwt.encode(
        {
            "sub": str(user["id"]),
            "email": user["email"],
            "role": user["role"],
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


# ── Schemas ─────────────────────────────────────────────────
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


# ── Endpoints ───────────────────────────────────────────────
@router.post("/register")
async def register(body: RegisterIn, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE lower(email)=lower($1)", body.email
        )
        if existing:
            raise HTTPException(409, "Email already registered")
        first = await conn.fetchval("SELECT COUNT(*) FROM users")
        role = "owner" if first == 0 else "viewer"
        verify_token = secrets.token_urlsafe(32)
        uid = await conn.fetchval(
            """INSERT INTO users (email, display_name, password_hash, role,
                                  email_verify_token, email_verified)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING id""",
            body.email.lower(), body.display_name, _hash_pw(body.password),
            role, verify_token, role == "owner",  # auto-verify the first owner
        )
    return {"status": "ok", "user_id": uid, "role": role,
            "verify_token": verify_token if role != "owner" else None}


@router.post("/login")
async def login(body: LoginIn, request: Request):
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
    access = _issue_jwt(dict(user))
    return {"status": "ok", "access_token": access, "refresh_token": raw,
            "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}


@router.post("/refresh")
async def refresh(body: RefreshIn):
    h = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT s.id, s.user_id, s.expires_at, s.revoked_at,
                  u.email, u.role, u.disabled
             FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.refresh_token_hash=$1""",
        h,
    )
    if not row or row["revoked_at"] is not None or row["expires_at"] < datetime.utcnow() or row["disabled"]:
        raise HTTPException(401, "Invalid refresh token")
    await pool.execute("UPDATE sessions SET last_seen_at=NOW() WHERE id=$1", row["id"])
    access = _issue_jwt({"id": row["user_id"], "email": row["email"], "role": row["role"]})
    return {"access_token": access}


@router.post("/logout")
async def logout(body: RefreshIn, _: Principal = Depends(principal_dep)):
    h = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    pool = await get_pool()
    await pool.execute(
        "UPDATE sessions SET revoked_at=NOW() WHERE refresh_token_hash=$1", h
    )
    return {"status": "ok"}


@router.get("/me")
async def me(p: Principal = Depends(principal_dep)):
    return {"data": {"user_id": p.user_id, "email": p.email, "role": p.role, "source": p.source}}


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
    # In dev/single-user we return the token so the user can complete the
    # reset without an email service. Production should email + return ok.
    return {"status": "ok", "reset_token": raw}


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
