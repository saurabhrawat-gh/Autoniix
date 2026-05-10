"""Provider/API management — Phase 2 (S3).

Endpoints:
  GET    /providers/categories
  GET    /providers/credentials?category=
  POST   /providers/credentials                   (writes secret to Vault)
  PUT    /providers/credentials/{id}
  DELETE /providers/credentials/{id}
  POST   /providers/credentials/{id}/test         (runs health_check)
  POST   /providers/credentials/{id}/rotate       (writes new value to Vault)
  GET    /providers/chains/{category}
  PUT    /providers/chains/{category}             (set ordered list of credential ids)
  GET    /providers/health/{credential_id}        (recent log)
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.db import get_pool
from src.providers.secrets import get_secret_at, put_secret_at

from ._deps import Principal, audit, principal_dep, require_role

router = APIRouter()


class CredentialIn(BaseModel):
    category: str
    provider_name: str
    label: str
    secret_value: str          # API key or token; write-only
    secret_key: str = "api_key"
    extra_config: dict = Field(default_factory=dict)


class CredentialPatch(BaseModel):
    label: str | None = None
    enabled: bool | None = None
    extra_config: dict | None = None


class RotateIn(BaseModel):
    secret_value: str
    secret_key: str = "api_key"


class ChainIn(BaseModel):
    credential_ids: list[int]


def _vault_path(category: str, provider_name: str, label: str) -> str:
    safe_label = "".join(c for c in label.lower() if c.isalnum() or c == "-") or "default"
    return f"providers/{category}/{provider_name}/{safe_label}"


# ── Categories ──────────────────────────────────────────────
@router.get("/categories")
async def list_categories(_: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT name, label, kind, description FROM provider_categories ORDER BY kind, name"
    )
    return {"data": [dict(r) for r in rows]}


# ── Credentials ─────────────────────────────────────────────
@router.get("/credentials")
async def list_credentials(
    category: str | None = None,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    if category:
        rows = await pool.fetch(
            """SELECT id, category, provider_name, label, vault_path, extra_config,
                      enabled, last_health_ok, last_health_at, last_latency_ms,
                      rotated_at, created_at
                 FROM provider_credentials WHERE category=$1 ORDER BY id""",
            category,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, category, provider_name, label, vault_path, extra_config,
                      enabled, last_health_ok, last_health_at, last_latency_ms,
                      rotated_at, created_at
                 FROM provider_credentials ORDER BY category, id"""
        )
    return {"data": [dict(r) for r in rows]}


@router.post("/credentials")
async def create_credential(
    body: CredentialIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    cat = await pool.fetchrow(
        "SELECT name FROM provider_categories WHERE name=$1", body.category
    )
    if not cat:
        raise HTTPException(400, f"Unknown category {body.category!r}")
    path = _vault_path(body.category, body.provider_name, body.label)

    backend_used = "env"
    try:
        backend_used = put_secret_at(path, body.secret_key, body.secret_value)
    except Exception as exc:
        raise HTTPException(500, f"Failed to store secret: {exc}")

    cid = await pool.fetchval(
        """INSERT INTO provider_credentials
            (category, provider_name, label, vault_path, extra_config, enabled, created_by)
           VALUES ($1,$2,$3,$4,$5::jsonb,TRUE,$6) RETURNING id""",
        body.category, body.provider_name, body.label, path,
        json.dumps(body.extra_config), actor.user_id,
    )
    await audit(actor=actor, action="provider.credential.create",
                target_type="provider_credential", target_id=str(cid),
                after={"category": body.category, "provider": body.provider_name,
                       "label": body.label, "backend": backend_used},
                request=request)
    return {"status": "ok", "id": cid, "vault_path": path, "backend": backend_used}


@router.put("/credentials/{credential_id}")
async def update_credential(
    credential_id: int,
    body: CredentialPatch,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "noop"}
    sets = []
    values: list[Any] = []
    for k, v in updates.items():
        sets.append(f"{k}=${len(values)+1}" + ("::jsonb" if k == "extra_config" else ""))
        values.append(json.dumps(v) if k == "extra_config" else v)
    values.append(credential_id)
    res = await pool.execute(
        f"UPDATE provider_credentials SET {', '.join(sets)}, updated_at=NOW() "
        f"WHERE id=${len(values)}",
        *values,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Credential not found")
    await audit(actor=actor, action="provider.credential.update",
                target_type="provider_credential", target_id=str(credential_id),
                after=updates, request=request)
    return {"status": "ok"}


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    res = await pool.execute(
        "DELETE FROM provider_credentials WHERE id=$1", credential_id
    )
    if res.endswith("0"):
        raise HTTPException(404, "Credential not found")
    await audit(actor=actor, action="provider.credential.delete",
                target_type="provider_credential", target_id=str(credential_id),
                request=request)
    return {"status": "ok"}


@router.post("/credentials/{credential_id}/test")
async def test_credential(
    credential_id: int,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT category, provider_name, vault_path, extra_config "
        "FROM provider_credentials WHERE id=$1",
        credential_id,
    )
    if not row:
        raise HTTPException(404, "Credential not found")

    secret = get_secret_at(row["vault_path"], "api_key")
    started = time.perf_counter()
    ok, error = False, None

    if not secret:
        error = "Secret not found in backend"
    else:
        try:
            from src.providers.registry import ProviderRegistry
            cls = ProviderRegistry._registries.get(row["category"], {}).get(row["provider_name"])
            if cls is None:
                error = f"Provider {row['provider_name']!r} not registered"
            else:
                inst = cls()
                hc = getattr(inst, "health_check", None)
                if hc is None:
                    ok = True  # No health_check → assume ok
                else:
                    res = hc()
                    if hasattr(res, "__await__"):
                        import asyncio
                        res = await res  # type: ignore[assignment]
                    ok = bool(res)
        except Exception as exc:
            error = str(exc)
    latency_ms = int((time.perf_counter() - started) * 1000)

    await pool.execute(
        """UPDATE provider_credentials
              SET last_health_ok=$1, last_health_at=NOW(), last_latency_ms=$2
            WHERE id=$3""",
        ok, latency_ms, credential_id,
    )
    await pool.execute(
        """INSERT INTO provider_health_log (credential_id, ok, latency_ms, error)
           VALUES ($1,$2,$3,$4)""",
        credential_id, ok, latency_ms, error,
    )
    await audit(actor=actor, action="provider.credential.test",
                target_type="provider_credential", target_id=str(credential_id),
                after={"ok": ok, "latency_ms": latency_ms, "error": error},
                request=request)
    return {"status": "ok", "data": {"ok": ok, "latency_ms": latency_ms, "error": error}}


@router.post("/credentials/{credential_id}/rotate")
async def rotate_credential(
    credential_id: int,
    body: RotateIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT vault_path FROM provider_credentials WHERE id=$1", credential_id
    )
    if not row:
        raise HTTPException(404, "Credential not found")
    try:
        backend = put_secret_at(row["vault_path"], body.secret_key, body.secret_value)
    except Exception as exc:
        raise HTTPException(500, f"Failed to rotate: {exc}")
    await pool.execute(
        "UPDATE provider_credentials SET rotated_at=NOW() WHERE id=$1", credential_id
    )
    # Reset chain cache so the next request picks up fresh creds.
    try:
        from src.providers.chain import reset_chain_cache
        from src.providers.registry import ProviderRegistry
        reset_chain_cache()
        ProviderRegistry.reset()
    except Exception:
        pass
    await audit(actor=actor, action="provider.credential.rotate",
                target_type="provider_credential", target_id=str(credential_id),
                after={"backend": backend}, request=request)
    return {"status": "ok"}


# ── Chains ──────────────────────────────────────────────────
@router.get("/chains/{category}")
async def get_chain(category: str, _: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT ppc.position, ppc.fallback_strategy,
                  pc.id AS credential_id, pc.label, pc.provider_name,
                  pc.enabled, pc.last_health_ok, pc.last_health_at
             FROM provider_priority_chains ppc
             JOIN provider_credentials pc ON pc.id = ppc.credential_id
            WHERE ppc.category=$1
            ORDER BY ppc.position""",
        category,
    )
    return {"data": [dict(r) for r in rows]}


@router.put("/chains/{category}")
async def set_chain(
    category: str,
    body: ChainIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM provider_priority_chains WHERE category=$1", category
            )
            for pos, cid in enumerate(body.credential_ids):
                await conn.execute(
                    """INSERT INTO provider_priority_chains
                            (category, position, credential_id)
                       VALUES ($1,$2,$3)""",
                    category, pos, cid,
                )
    try:
        from src.providers.chain import reset_chain_cache
        from src.providers.registry import ProviderRegistry
        reset_chain_cache()
        ProviderRegistry.reset()
    except Exception:
        pass
    await audit(actor=actor, action="provider.chain.set",
                target_type="provider_chain", target_id=category,
                after={"credential_ids": body.credential_ids}, request=request)
    return {"status": "ok"}


@router.get("/health/{credential_id}")
async def credential_health(
    credential_id: int, limit: int = 50,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT ok, latency_ms, error, checked_at
             FROM provider_health_log
            WHERE credential_id=$1
            ORDER BY checked_at DESC LIMIT $2""",
        credential_id, limit,
    )
    return {"data": [dict(r) for r in rows]}
