"""Shared dependencies for v2 routers.

Single source of truth for auth, audit logging, and feature-flag checks.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.db import get_pool

logger = structlog.get_logger()

_security = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    """Authenticated subject. ``user_id`` is None for legacy single-user."""
    user_id: int | None
    email: str | None
    role: str
    source: str  # 'legacy' | 'v2_jwt'


def _jwt_secret() -> str:
    return os.getenv("AUTH_JWT_SECRET") or os.getenv("DASHBOARD_JWT_SECRET") or "dev-insecure-change-me"


def _decode_jwt(token: str) -> dict[str, Any] | None:
    try:
        import jwt  # PyJWT
        return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except Exception:
        return None


async def principal_dep(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_security),
) -> Principal:
    """Resolve a Principal from either legacy session or v2 JWT.

    Order:
      1. v2 JWT (looks like a JWT — starts with ``ey`` and has 2 dots).
      2. Legacy in-memory session map from ``main._sessions`` (backwards-compat).
    """
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = creds.credentials

    if token.count(".") == 2 and token.startswith("ey"):
        claims = _decode_jwt(token)
        if claims:
            return Principal(
                user_id=int(claims["sub"]) if "sub" in claims else None,
                email=claims.get("email"),
                role=claims.get("role", "viewer"),
                source="v2_jwt",
            )

    # Legacy fallback
    try:
        from src.services.dashboard import main as _legacy
        import time as _time
        expiry = _legacy._sessions.get(token)
        if expiry is not None and expiry >= _time.time():
            return Principal(user_id=None, email=None, role="owner", source="legacy")
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_role(*roles: str):
    """Dependency factory enforcing a role allowlist."""
    allowed = set(roles)

    async def _checker(p: Principal = Depends(principal_dep)) -> Principal:
        if p.role not in allowed and p.role != "owner":
            raise HTTPException(status_code=403, detail=f"Role {p.role!r} not allowed")
        return p

    return _checker


# ── Feature flags ───────────────────────────────────────────
async def flag_enabled(key: str) -> bool:
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT enabled FROM feature_flags WHERE key = $1", key
        )
        return bool(row and row["enabled"])
    except Exception:
        return False


# ── Audit logging ──────────────────────────────────────────
async def audit(
    *,
    actor: Principal,
    action: str,
    target_type: str,
    target_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    request: Request | None = None,
) -> None:
    """Append-only audit row. Best-effort — never raises."""
    try:
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO audit_log_v2
                (actor_user_id, actor_label, action, target_type, target_id,
                 before, after, source, request_id, ip, user_agent)
            VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8,$9,$10,$11)
            """,
            actor.user_id,
            actor.email or actor.source,
            action,
            target_type,
            target_id,
            json.dumps(before) if before is not None else None,
            json.dumps(after) if after is not None else None,
            "ui" if (request and request.headers.get("x-source") == "ui") else "api",
            (request.headers.get("x-request-id") if request else None),
            (request.client.host if request and request.client else None),
            (request.headers.get("user-agent") if request else None),
        )
    except Exception as exc:
        logger.warning("audit.write_failed", action=action, error=str(exc))
