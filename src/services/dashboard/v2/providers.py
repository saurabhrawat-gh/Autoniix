"""Provider/API management — Wave 2 (full provider operations center).

Phase 2 (S3) endpoints (existing):
  GET    /providers/categories
  GET    /providers/credentials?category=
  POST   /providers/credentials
  PUT    /providers/credentials/{id}
  DELETE /providers/credentials/{id}
  POST   /providers/credentials/{id}/test
  POST   /providers/credentials/{id}/rotate
  GET    /providers/chains/{category}
  PUT    /providers/chains/{category}
  GET    /providers/health/{credential_id}

Wave 2 additions:
  GET    /providers/marketplace                   (catalog with connected status)
  POST   /providers/health/probe-all              (fan-out health check all enabled creds)
  GET    /providers/routes?scope=&scope_id=       (routing policies)
  PUT    /providers/routes/{category}             (set routing policy for category at scope)
  GET    /providers/quotas?scope=&scope_id=       (quota summary list)
  PUT    /providers/quotas/{id}                   (update quota cap/policy)
  POST   /providers/sandbox/run                   (run test inference)
  GET    /providers/sandbox/runs?credential_id=   (recent sandbox run history)
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.db import get_pool
from src.providers.invalidation import publish_invalidate
from src.providers.secrets import get_secret_at, put_secret_at

from ._deps import Principal, audit, flag_enabled, principal_dep, require_role

router = APIRouter()


async def _require_cred_actor(p: Principal = Depends(principal_dep)) -> Principal:
    """Owner always allowed; Admin allowed only when providers.admin_credentials.enabled is ON."""
    if p.role == "owner":
        return p
    if p.role == "admin" and await flag_enabled("providers.admin_credentials.enabled"):
        return p
    raise HTTPException(
        403,
        "Owner role required. Admins can be granted access via the "
        "'providers.admin_credentials.enabled' feature flag.",
    )


class CredentialIn(BaseModel):
    category: str
    provider_name: str
    label: str
    secret_value: str = ""    # API key or token; write-only. Empty = no-key provider.
    secret_key: str = "api_key"
    model: str | None = None   # pinned model (validated against supported_models())
    extra_config: dict = Field(default_factory=dict)
    channel_id: str | None = None    # NULL = workspace-level
    content_mode: str | None = None  # NULL = all modes


class WizardCredentialIn(BaseModel):
    """Flat form body from the catalog wizard.

    The wizard POSTs all form fields in ``wizard_fields``; this endpoint
    splits them into secret vault entries and ``extra_config`` using the
    provider's ``config_schema`` from ``provider_marketplace_catalog``.
    """
    category: str
    provider_key: str           # matches provider_marketplace_catalog.provider_key
    label: str
    wizard_fields: dict         # {field_name: value} from the wizard form
    model: str | None = None
    channel_id: str | None = None
    content_mode: str | None = None


class CredentialPatch(BaseModel):
    label: str | None = None
    enabled: bool | None = None
    model: str | None = None
    extra_config: dict | None = None


class RotateIn(BaseModel):
    secret_value: str
    secret_key: str = "api_key"
    hint: str | None = None   # human note stored in rotation_hint column


class ChainIn(BaseModel):
    credential_ids: list[int]


def _vault_path(category: str, provider_name: str, label: str) -> str:
    safe_label = "".join(c for c in label.lower() if c.isalnum() or c == "-") or "default"
    return f"providers/{category}/{provider_name}/{safe_label}"


# Categories
@router.get("/categories")
async def list_categories(_: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT name, label, kind, description FROM provider_categories ORDER BY kind, name"
    )
    return {"data": [dict(r) for r in rows]}


# Credentials
@router.get("/credentials")
async def list_credentials(
    category: str | None = None,
    channel_id: str | None = Query(None),
    content_mode: str | None = Query(None),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    filters = []
    args: list[Any] = []
    if category:
        args.append(category)
        filters.append(f"category=${len(args)}")
    if channel_id is not None:
        args.append(channel_id)
        filters.append(f"channel_id=${len(args)}")
    if content_mode is not None:
        args.append(content_mode)
        filters.append(f"content_mode=${len(args)}")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = await pool.fetch(
        f"""SELECT id, category, provider_name, label, vault_path, extra_config,
                  model, is_default_fallback, channel_id, content_mode, scope_priority,
                  enabled, last_health_ok, last_health_at, last_latency_ms,
                  rotated_at, created_at
             FROM provider_credentials {where}
            ORDER BY category, scope_priority DESC, id""",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/credentials")
async def create_credential(
    body: CredentialIn,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    pool = await get_pool()
    cat = await pool.fetchrow(
        "SELECT name FROM provider_categories WHERE name=$1", body.category
    )
    if not cat:
        raise HTTPException(400, f"Unknown category {body.category!r}")

    # Reject unknown provider_name hard: there's no future in which a
    # credential pointing at an unregistered class can actually be
    # used (test/health/runtime all fail with "Unknown provider").
    # The UI ships a dropdown of registered names, so a 400 here means
    # someone bypassed it via curl / typo.
    try:
        from src.providers.registry import ProviderRegistry
        registered = ProviderRegistry._registries.get(body.category, {})
        if body.provider_name not in registered:
            available = sorted(registered.keys())
            raise HTTPException(
                400,
                f"Provider {body.provider_name!r} is not registered for "
                f"category {body.category!r}. Available: {available or '(none)'}. "
                f"Pick one from the dropdown.",
            )
    except HTTPException:
        raise
    except Exception:
        # Registry import failed (very rare) — fall open rather than
        # block all writes.
        pass

    # If a model was specified, validate it against the live provider's
    # supported_models() so a typo can't silently route to the wrong model.
    if body.model:
        _validate_model(body.category, body.provider_name, body.model)

    path = _vault_path(body.category, body.provider_name, body.label)

    if body.secret_value:
        backend_used = "env"
        try:
            backend_used = put_secret_at(path, body.secret_key, body.secret_value)
        except Exception as exc:
            raise HTTPException(500, f"Failed to store secret: {exc}")
    else:
        backend_used = "none"

    scope_priority = 0
    if body.channel_id and body.content_mode:
        scope_priority = 20
    elif body.channel_id:
        scope_priority = 10

    cid = await pool.fetchval(
        """INSERT INTO provider_credentials
            (category, provider_name, label, vault_path, extra_config, model,
             channel_id, content_mode, scope_priority, enabled, created_by)
           VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,TRUE,$10) RETURNING id""",
        body.category, body.provider_name, body.label, path,
        json.dumps(body.extra_config), body.model,
        body.channel_id, body.content_mode, scope_priority, actor.user_id,
    )
    await audit(actor=actor, action="provider.credential.create",
                target_type="provider_credential", target_id=str(cid),
                after={"category": body.category, "provider": body.provider_name,
                       "label": body.label, "model": body.model,
                       "channel_id": body.channel_id, "content_mode": body.content_mode,
                       "backend": backend_used},
                request=request)
    await publish_invalidate(category=body.category)
    return {"status": "ok", "id": cid, "vault_path": path, "backend": backend_used}


@router.post("/credentials/from-wizard")
async def create_credential_from_wizard(
    body: WizardCredentialIn,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Catalog-wizard endpoint. Splits ``wizard_fields`` into vault secrets and
    extra_config using the provider's ``config_schema``, then delegates to the
    standard credential creation logic.

    Password-type fields → stored in vault (only the first one used as api_key).
    All other field types → stored in extra_config for the provider to read.
    """
    pool = await get_pool()
    catalog_row = await pool.fetchrow(
        """SELECT config_schema, category, provider_key
             FROM provider_marketplace_catalog WHERE provider_key=$1""",
        body.provider_key,
    )
    if not catalog_row:
        raise HTTPException(400, f"Unknown provider_key {body.provider_key!r}")

    schema: list[dict] = catalog_row["config_schema"] or []

    # Validate required fields
    missing = [
        f["name"]
        for f in schema
        if f.get("required") and not body.wizard_fields.get(f["name"])
    ]
    if missing:
        raise HTTPException(
            422,
            f"Required wizard field(s) missing: {', '.join(missing)}",
        )

    # Split fields: password type → vault secret; others → extra_config
    secret_value = ""
    secret_key = "api_key"
    extra_config: dict = {}
    for field in schema:
        name = field["name"]
        value = body.wizard_fields.get(name)
        if value is None:
            continue
        if field.get("type") == "password":
            if not secret_value:   # only first password field is the primary key
                secret_value = str(value)
                secret_key = name
        else:
            extra_config[name] = value

    cred_in = CredentialIn(
        category=body.category,
        provider_name=body.provider_key,
        label=body.label,
        secret_value=secret_value,
        secret_key=secret_key,
        model=body.model,
        extra_config=extra_config,
        channel_id=body.channel_id,
        content_mode=body.content_mode,
    )
    # Reuse the standard create flow by directly calling the helper
    return await create_credential(cred_in, request, actor)


@router.put("/credentials/{credential_id}")
async def update_credential(
    credential_id: int,
    body: CredentialPatch,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    pool = await get_pool()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "noop"}

    if "model" in updates and updates["model"]:
        cred = await pool.fetchrow(
            "SELECT category, provider_name FROM provider_credentials WHERE id=$1",
            credential_id,
        )
        if not cred:
            raise HTTPException(404, "Credential not found")
        _validate_model(cred["category"], cred["provider_name"], updates["model"])

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
    cat_row = await pool.fetchrow(
        "SELECT category FROM provider_credentials WHERE id=$1", credential_id,
    )
    await audit(actor=actor, action="provider.credential.update",
                target_type="provider_credential", target_id=str(credential_id),
                after=updates, request=request)
    if cat_row:
        await publish_invalidate(category=cat_row["category"])
    return {"status": "ok"}


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    pool = await get_pool()
    cat_row = await pool.fetchrow(
        "SELECT category FROM provider_credentials WHERE id=$1", credential_id,
    )
    res = await pool.execute(
        "DELETE FROM provider_credentials WHERE id=$1", credential_id
    )
    if res.endswith("0"):
        raise HTTPException(404, "Credential not found")
    await audit(actor=actor, action="provider.credential.delete",
                target_type="provider_credential", target_id=str(credential_id),
                request=request)
    if cat_row:
        await publish_invalidate(category=cat_row["category"])
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
    actor: Principal = Depends(_require_cred_actor),
):
    if not await flag_enabled("providers.credentials.rotate.enabled"):
        raise HTTPException(403, "Credential rotation is disabled")
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, vault_path, category, provider_name, label, extra_config "
        "FROM provider_credentials WHERE id=$1", credential_id
    )
    if not row:
        raise HTTPException(404, "Credential not found")

    # --- Safe-swap: write to a staging path, verify, then promote ---
    staging_path = row["vault_path"] + "/__staging__"
    try:
        put_secret_at(staging_path, body.secret_key, body.secret_value)
    except Exception as exc:
        raise HTTPException(500, f"Failed to stage new secret: {exc}")

    # Verify the new key by instantiating the provider with the staged secret
    health_ok = False
    health_error: str | None = None
    try:
        from src.providers.registry import ProviderRegistry
        cls = ProviderRegistry._registries.get(row["category"], {}).get(row["provider_name"])
        if cls is None:
            health_error = f"Provider {row['provider_name']!r} not registered; skipping verification"
            health_ok = True  # fall-open: can't verify unregistered provider
        else:
            test_inst = cls()
            staged_key = get_secret_at(staging_path, body.secret_key)
            if staged_key and hasattr(test_inst, "api_key") and not getattr(test_inst, "api_key", None):
                test_inst.api_key = staged_key
            for k, v in (row.get("extra_config") or {}).items():
                try:
                    setattr(test_inst, k, v)
                except Exception:
                    pass
            if hasattr(test_inst, "_connect") and callable(test_inst._connect):
                try:
                    test_inst._connect()
                except Exception:
                    pass
            hc = getattr(test_inst, "health_check", None)
            if hc is None:
                health_ok = True
            else:
                res = hc()
                if hasattr(res, "__await__"):
                    res = await res  # type: ignore[assignment]
                health_ok = bool(res)
    except Exception as exc:
        health_error = str(exc)
        health_ok = False

    if not health_ok:
        raise HTTPException(
            422,
            f"New credential failed health check — rotation aborted. "
            f"Error: {health_error or 'health_check returned False'}. "
            f"The old credential is still active.",
        )

    # Health check passed — promote staged key to live path
    try:
        backend = put_secret_at(row["vault_path"], body.secret_key, body.secret_value)
    except Exception as exc:
        raise HTTPException(500, f"Failed to promote rotated secret: {exc}")

    await pool.execute(
        "UPDATE provider_credentials SET rotated_at=NOW(), rotation_hint=$2 WHERE id=$1",
        credential_id, body.hint,
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
                after={"backend": backend, "hint": body.hint}, request=request)
    if cat_row := await pool.fetchrow(
        "SELECT category FROM provider_credentials WHERE id=$1", credential_id,
    ):
        await publish_invalidate(category=cat_row["category"])
    return {"status": "ok", "backend": backend}


# ── Rotation status ──────────────────────────────────────────────────────────
ROTATION_WARN_DAYS = 30   # flag as overdue after this many days without rotation


@router.get("/credentials/{credential_id}/rotation-status")
async def credential_rotation_status(
    credential_id: int,
    _: Principal = Depends(principal_dep),
):
    """Return rotation age and overdue flag for a single credential."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, label, category, provider_name, rotated_at, rotation_hint, created_at
             FROM provider_credentials WHERE id=$1""",
        credential_id,
    )
    if not row:
        raise HTTPException(404, "Credential not found")
    return _rotation_status_dict(row)


@router.get("/credentials/rotation-status")
async def all_credentials_rotation_status(
    category: str | None = None,
    overdue_only: bool = False,
    _: Principal = Depends(principal_dep),
):
    """Return rotation age for all (or a category's) credentials."""
    pool = await get_pool()
    where = "WHERE 1=1"
    args: list[Any] = []
    if category:
        args.append(category)
        where += f" AND category=${len(args)}"
    rows = await pool.fetch(
        f"""SELECT id, label, category, provider_name, rotated_at, rotation_hint, created_at
              FROM provider_credentials {where}
             ORDER BY category, id""",
        *args,
    )
    items = [_rotation_status_dict(r) for r in rows]
    if overdue_only:
        items = [i for i in items if i["overdue"]]
    return {"data": items}


def _rotation_status_dict(row: Any) -> dict:
    import datetime
    from zoneinfo import ZoneInfo

    now = datetime.datetime.now(tz=ZoneInfo("UTC"))
    anchor = row["rotated_at"] or row["created_at"]
    days_since: int | None = None
    if anchor:
        delta = now - anchor.replace(tzinfo=ZoneInfo("UTC")) if anchor.tzinfo is None else now - anchor
        days_since = delta.days
    overdue = days_since is not None and days_since >= ROTATION_WARN_DAYS
    return {
        "id": row["id"],
        "label": row["label"],
        "category": row["category"],
        "provider_name": row["provider_name"],
        "rotated_at": row["rotated_at"].isoformat() if row["rotated_at"] else None,
        "rotation_hint": row["rotation_hint"],
        "days_since_rotation": days_since,
        "overdue": overdue,
        "warn_after_days": ROTATION_WARN_DAYS,
    }


# Chains (legacy URL — proxies to v2 workspace+mode-agnostic)
@router.get("/chains/{category}")
async def get_chain(category: str, _: Principal = Depends(principal_dep)):
    """Legacy endpoint. Returns the workspace + mode-agnostic chain for the category."""
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT c.id, c.position, c.fallback_strategy,
                  COALESCE(c.is_enabled, TRUE) AS is_enabled,
                  pc.id AS credential_id, pc.label, pc.provider_name, pc.model,
                  pc.enabled, pc.last_health_ok, pc.last_health_at
             FROM provider_chains_v2 c
             JOIN provider_credentials pc ON pc.id = c.credential_id
            WHERE c.scope = 'workspace' AND c.scope_id IS NULL
              AND c.content_mode IS NULL AND c.category = $1
            ORDER BY c.position""",
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
    """Legacy endpoint. Writes the workspace + mode-agnostic chain for the category."""
    await _upsert_chain_v2(
        scope="workspace", scope_id=None, content_mode=None,
        category=category, credential_ids=body.credential_ids,
        actor_user_id=actor.user_id,
    )
    await audit(actor=actor, action="provider.chain.set",
                target_type="provider_chain", target_id=category,
                after={"scope": "workspace", "credential_ids": body.credential_ids},
                request=request)
    await publish_invalidate(category=category)
    return {"status": "ok"}


# Chains v2 (scope + content-mode aware)
class ChainV2In(BaseModel):
    scope: str = "workspace"           # system|workspace|brand|channel|project
    scope_id: str | None = None
    content_mode: str | None = None    # NULL = applies to all modes
    pipeline_mode: str = "production"  # production|test
    category: str
    credential_ids: list[int] = Field(default_factory=list)


@router.get("/chains")
async def list_chain_v2(
    scope: str = "workspace",
    scope_id: str | None = None,
    content_mode: str | None = None,
    pipeline_mode: str = "production",
    category: str | None = None,
    _: Principal = Depends(principal_dep),
):
    """List chain rows for a given (scope, scope_id, content_mode, pipeline_mode, [category])."""
    pool = await get_pool()
    sql = """SELECT c.id, c.scope, c.scope_id, c.content_mode, c.pipeline_mode, c.category,
                    c.position, c.fallback_strategy,
                    COALESCE(c.is_enabled, TRUE) AS is_enabled,
                    pc.id AS credential_id, pc.label, pc.provider_name, pc.model,
                    pc.enabled, pc.last_health_ok, pc.last_health_at
               FROM provider_chains_v2 c
               JOIN provider_credentials pc ON pc.id = c.credential_id
              WHERE c.scope = $1
                AND ($2::text IS NULL AND c.scope_id IS NULL OR c.scope_id = $2)
                AND ($3::text IS NULL AND c.content_mode IS NULL OR c.content_mode = $3)
                AND COALESCE(c.pipeline_mode, 'production') = $4"""
    args: list[Any] = [scope, scope_id, content_mode, pipeline_mode]
    if category:
        sql += " AND c.category = $5"
        args.append(category)
    sql += " ORDER BY c.category, c.position"
    rows = await pool.fetch(sql, *args)
    return {"data": [dict(r) for r in rows]}


@router.put("/chains")
async def upsert_chain_v2(
    body: ChainV2In,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    """Replace the chain at (scope, scope_id, content_mode, pipeline_mode, category)."""
    await _upsert_chain_v2(
        scope=body.scope, scope_id=body.scope_id, content_mode=body.content_mode,
        pipeline_mode=body.pipeline_mode, category=body.category,
        credential_ids=body.credential_ids, actor_user_id=actor.user_id,
    )
    await audit(actor=actor, action="provider.chain_v2.set",
                target_type="provider_chain_v2",
                target_id=f"{body.scope}:{body.scope_id or ''}:{body.content_mode or ''}:{body.pipeline_mode}:{body.category}",
                after=body.model_dump(), request=request)
    await publish_invalidate(
        category=body.category,
        channel_id=body.scope_id if body.scope == "channel" else None,
        content_mode=body.content_mode,
    )
    return {"status": "ok"}


@router.delete("/chains")
async def delete_chain_v2(
    scope: str,
    category: str,
    scope_id: str | None = None,
    content_mode: str | None = None,
    pipeline_mode: str = "production",
    request: Request = None,  # type: ignore[assignment]
    actor: Principal = Depends(require_role("owner", "admin")),
):
    """Remove an override layer so resolution falls through to the next layer up."""
    pool = await get_pool()
    await pool.execute(
        """DELETE FROM provider_chains_v2
            WHERE scope = $1
              AND ($2::text IS NULL AND scope_id IS NULL OR scope_id = $2)
              AND ($3::text IS NULL AND content_mode IS NULL OR content_mode = $3)
              AND COALESCE(pipeline_mode, 'production') = $4
              AND category = $5""",
        scope, scope_id, content_mode, pipeline_mode, category,
    )
    await audit(actor=actor, action="provider.chain_v2.delete",
                target_type="provider_chain_v2",
                target_id=f"{scope}:{scope_id or ''}:{content_mode or ''}:{pipeline_mode}:{category}",
                request=request)
    await publish_invalidate(
        category=category,
        channel_id=scope_id if scope == "channel" else None,
        content_mode=content_mode,
    )
    return {"status": "ok"}


async def _upsert_chain_v2(
    *,
    scope: str,
    scope_id: str | None,
    content_mode: str | None,
    pipeline_mode: str = "production",
    category: str,
    credential_ids: list[int],
    actor_user_id: int | None,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM provider_chains_v2
                    WHERE scope = $1
                      AND ($2::text IS NULL AND scope_id IS NULL OR scope_id = $2)
                      AND ($3::text IS NULL AND content_mode IS NULL OR content_mode = $3)
                      AND COALESCE(pipeline_mode, 'production') = $4
                      AND category = $5""",
                scope, scope_id, content_mode, pipeline_mode, category,
            )
            for pos, cid in enumerate(credential_ids):
                await conn.execute(
                    """INSERT INTO provider_chains_v2
                            (scope, scope_id, content_mode, pipeline_mode, category, position,
                             credential_id, created_by)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                    scope, scope_id, content_mode, pipeline_mode, category, pos, cid, actor_user_id,
                )


def _validate_model(category: str, provider_name: str, model: str) -> None:
    """Reject typos / unsupported models against the live provider class.

    Falls open if the provider hasn't registered (e.g. still booting),
    so workspaces can configure credentials before the worker fleet is
    fully up. The chain resolver is the runtime authority either way.
    """
    try:
        from src.providers.registry import ProviderRegistry
        cls = ProviderRegistry._registries.get(category, {}).get(provider_name)
        if cls is None:
            return
        try:
            inst = cls()
        except Exception:
            return
        supported = []
        try:
            sm = getattr(inst, "supported_models", None)
            if callable(sm):
                supported = list(sm() or [])
        except Exception:
            return
        if supported and model not in supported:
            raise HTTPException(
                400,
                f"Model {model!r} not supported by {provider_name!r}. "
                f"Supported: {supported}",
            )
    except HTTPException:
        raise
    except Exception:
        # Don't block writes on validation infra failures.
        return


# Default fallback
@router.put("/credentials/{credential_id}/default-fallback")
async def set_default_fallback(
    credential_id: int,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    """Mark this credential as the always-tried-last fallback for its category.

    The unique partial index on `provider_credentials(category) WHERE
    is_default_fallback` guarantees at most one per category, so we
    explicitly clear any existing flag in the same transaction.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            cred = await conn.fetchrow(
                "SELECT category FROM provider_credentials WHERE id=$1",
                credential_id,
            )
            if not cred:
                raise HTTPException(404, "Credential not found")
            await conn.execute(
                "UPDATE provider_credentials SET is_default_fallback=FALSE "
                "WHERE category=$1 AND is_default_fallback=TRUE",
                cred["category"],
            )
            await conn.execute(
                "UPDATE provider_credentials SET is_default_fallback=TRUE "
                "WHERE id=$1",
                credential_id,
            )
    await audit(actor=actor, action="provider.credential.default_fallback",
                target_type="provider_credential", target_id=str(credential_id),
                after={"category": cred["category"]}, request=request)
    await publish_invalidate(category=cred["category"])
    return {"status": "ok"}


@router.delete("/credentials/{credential_id}/default-fallback")
async def clear_default_fallback(
    credential_id: int,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    """Unset the default-fallback flag on this credential."""
    pool = await get_pool()
    cred = await pool.fetchrow(
        "SELECT category FROM provider_credentials WHERE id=$1", credential_id,
    )
    if not cred:
        raise HTTPException(404, "Credential not found")
    await pool.execute(
        "UPDATE provider_credentials SET is_default_fallback=FALSE WHERE id=$1",
        credential_id,
    )
    await audit(actor=actor, action="provider.credential.default_fallback_clear",
                target_type="provider_credential", target_id=str(credential_id),
                request=request)
    await publish_invalidate(category=cred["category"])
    return {"status": "ok"}


# Content modes
@router.get("/content-modes")
async def list_content_modes(_: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT name, label, description, sort_order, is_system "
        "FROM content_modes ORDER BY sort_order, name"
    )
    return {"data": [dict(r) for r in rows]}


# Registered providers for a category
# Hardcoded fallback display names for provider keys whose marketplace
# catalog entry uses a different key (`claude` ↔ `anthropic`) or that
# aren't catalogued yet. Source of truth: provider_marketplace_catalog.
_PROVIDER_DISPLAY_FALLBACK: dict[str, str] = {
    "openai":        "OpenAI",
    "claude":        "Anthropic (Claude)",
    "anthropic":     "Anthropic (Claude)",
    "gemini":        "Google Gemini",
    "groq":          "Groq",
    "ollama":        "Ollama (local)",
    "glm":           "Zhipu (GLM)",
    "kimi":          "Moonshot (Kimi)",
    "mistral":       "Mistral AI",
    "deepseek":      "DeepSeek",
    "qwen":          "Alibaba (Qwen)",
    "mock_llm":      "Mock LLM (test only)",
    "elevenlabs":    "ElevenLabs",
    "fish_audio":    "Fish Audio",
    "fishaudio":     "Fish Audio",
    "edge_tts":      "Microsoft Edge TTS",
    "dalle":         "OpenAI DALL·E",
    "placeholder":   "Placeholder (test only)",
    "serpapi":       "SerpAPI",
    "mock_search":   "Mock search (test only)",
    "minio":         "MinIO / S3-compatible",
}


@router.get("/registered")
async def registered_providers_endpoint(
    category: str,
    _: Principal = Depends(principal_dep),
):
    """Return the list of provider classes registered in-process for
    a given category, each with their default + supported models and
    a human-readable display name.

    The Add Credential modal uses this to populate the provider
    dropdown so users can't type a garbage `provider_name` that the
    runtime would never be able to instantiate.

    Display name resolution order:
      1. provider_marketplace_catalog.display_name (DB)
      2. _PROVIDER_DISPLAY_FALLBACK (hardcoded for un-catalogued keys)
      3. title-cased provider_key
    """
    try:
        from src.providers.registry import ProviderRegistry
        registry = ProviderRegistry._registries.get(category, {})
    except Exception as exc:  # noqa: BLE001
        return {"data": [], "error": str(exc)}

    # Pre-fetch marketplace display names in one query.
    pool = await get_pool()
    catalog_rows = await pool.fetch(
        "SELECT provider_key, display_name, logo_url, website_url, has_free_tier "
        "FROM provider_marketplace_catalog"
    )
    catalog: dict[str, dict] = {r["provider_key"]: dict(r) for r in catalog_rows}

    out: list[dict] = []
    for name in sorted(registry.keys()):
        cls = registry[name]
        default: str | None = None
        models: list[str] = []
        try:
            inst = cls()
            sm = getattr(inst, "supported_models", None)
            if callable(sm):
                models = list(sm() or [])
            dm = getattr(inst, "default_model", None)
            if callable(dm):
                try:
                    default = dm()
                except Exception:
                    default = None
        except Exception:
            pass

        cat_entry = catalog.get(name) or {}
        display_name = (
            cat_entry.get("display_name")
            or _PROVIDER_DISPLAY_FALLBACK.get(name)
            or name.replace("_", " ").title()
        )
        out.append({
            "provider_name": name,
            "display_name": display_name,
            "logo_url": cat_entry.get("logo_url"),
            "website_url": cat_entry.get("website_url"),
            "has_free_tier": cat_entry.get("has_free_tier"),
            "default_model": default,
            "supported_models": models,
        })
    return {"data": out}


# Supported models for a registered provider
@router.get("/models")
async def supported_models_endpoint(
    category: str,
    provider_name: str,
    _: Principal = Depends(principal_dep),
):
    """Return the live `supported_models()` list for the registered class.

    Empty list when the provider isn't registered (e.g. still booting),
    so the UI can fall back to a free-text input.
    """
    try:
        from src.providers.registry import ProviderRegistry
        cls = ProviderRegistry._registries.get(category, {}).get(provider_name)
        if cls is None:
            return {"data": [], "registered": False}
        inst = cls()
        sm = getattr(inst, "supported_models", None)
        models = list(sm() or []) if callable(sm) else []
        default = None
        dm = getattr(inst, "default_model", None)
        if callable(dm):
            try:
                default = dm()
            except Exception:
                default = None
        return {"data": models, "default": default, "registered": True}
    except Exception as exc:  # noqa: BLE001
        return {"data": [], "registered": False, "error": str(exc)}


# Effective chain (debug + UI rendering)
@router.get("/resolved")
async def resolved_chain(
    category: str,
    channel_id: str | None = None,
    content_mode: str | None = None,
    pipeline_mode: str = "production",
    _: Principal = Depends(principal_dep),
):
    """Return the merged chain that the runtime would use for this lookup.

    Resolution mirrors `src/providers/chain.py`:
        channel+mode > channel > workspace+mode > workspace > system > default

    Each entry includes an `origin` label so the UI can show why each
    credential is in the chain.
    """
    pool = await get_pool()

    layers: list[tuple[str, str | None, str | None, str]] = []
    if channel_id:
        if content_mode:
            layers.append(("channel", channel_id, content_mode, "channel+mode"))
        layers.append(("channel", channel_id, None, "channel"))
    if content_mode:
        layers.append(("workspace", None, content_mode, "workspace+mode"))
    layers.append(("workspace", None, None, "workspace"))
    layers.append(("system", None, None, "system"))

    seen: set[int] = set()
    out: list[dict] = []
    async with pool.acquire() as conn:
        for scope, sid, mode, origin in layers:
            rows = await conn.fetch(
                """SELECT c.id AS chain_entry_id, c.position, c.fallback_strategy,
                          COALESCE(c.is_enabled, TRUE) AS is_enabled,
                          pc.id AS credential_id, pc.label, pc.provider_name,
                          pc.model, pc.enabled, pc.last_health_ok
                     FROM provider_chains_v2 c
                     JOIN provider_credentials pc ON pc.id = c.credential_id
                    WHERE c.scope = $1
                      AND ($2::text IS NULL AND c.scope_id IS NULL OR c.scope_id = $2)
                      AND ($3::text IS NULL AND c.content_mode IS NULL OR c.content_mode = $3)
                      AND c.category = $4
                      AND COALESCE(c.pipeline_mode, 'production') = $5
                      AND pc.enabled = TRUE
                      AND COALESCE(c.is_enabled, TRUE) = TRUE
                    ORDER BY c.position""",
                scope, sid, mode, category, pipeline_mode,
            )
            for r in rows:
                if r["credential_id"] in seen:
                    continue
                seen.add(r["credential_id"])
                out.append({**dict(r), "origin": origin})

        # Default fallback always appended last.
        fb = await conn.fetchrow(
            """SELECT id AS credential_id, label, provider_name, model,
                      enabled, last_health_ok
                 FROM provider_credentials
                WHERE category = $1 AND is_default_fallback = TRUE AND enabled = TRUE
                LIMIT 1""",
            category,
        )
        if fb and fb["credential_id"] not in seen:
            seen.add(fb["credential_id"])
            out.append({**dict(fb), "origin": "default", "position": None,
                        "fallback_strategy": "always"})

    return {
        "data": out,
        "category": category,
        "channel_id": channel_id,
        "content_mode": content_mode,
        "pipeline_mode": pipeline_mode,
    }


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


# Wave 2 — Marketplace, Routing, Quotas, Sandbox, Probe-all

# Marketplace

@router.get("/marketplace")
async def list_marketplace(_: Principal = Depends(principal_dep)):
    """Return full provider catalog with `connected` flag for each entry."""
    pool = await get_pool()
    catalog = await pool.fetch(
        """SELECT id, provider_key, display_name, category, description,
                  logo_url, website_url, mode, capabilities, pricing_notes,
                  cost_unit, regions, has_free_tier, featured, sort_order,
                  config_schema, supported_models, pricing_tier, docs_url,
                  is_platform_seeded
             FROM provider_marketplace_catalog
            ORDER BY category, sort_order, display_name"""
    )
    # Which provider_names are already connected?
    connected_rows = await pool.fetch(
        "SELECT DISTINCT provider_name FROM provider_credentials WHERE enabled=TRUE"
    )
    connected = {r["provider_name"] for r in connected_rows}
    result = []
    for r in catalog:
        d = dict(r)
        d["connected"] = r["provider_key"] in connected
        result.append(d)
    return {"data": result}


@router.get("/setup-checklist")
async def setup_checklist(_: Principal = Depends(principal_dep)):
    """Return setup progress across all required provider categories."""
    pool = await get_pool()
    categories = await pool.fetch(
        "SELECT name FROM provider_categories ORDER BY name"
    )
    result = []
    total_ok = 0
    for cat in categories:
        cname = cat["name"]
        cred = await pool.fetchrow(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN enabled THEN 1 ELSE 0 END) AS enabled_count,
                      SUM(CASE WHEN last_health_ok THEN 1 ELSE 0 END) AS healthy_count
                 FROM provider_credentials WHERE category=$1""",
            cname,
        )
        chain = await pool.fetchrow(
            "SELECT COUNT(*) AS chain_entries FROM provider_chains_v2 WHERE category=$1",
            cname,
        )
        ok = bool(cred["enabled_count"] and cred["enabled_count"] > 0)
        if ok:
            total_ok += 1
        result.append({
            "category": cname,
            "credentials": int(cred["total"] or 0),
            "enabled": int(cred["enabled_count"] or 0),
            "healthy": int(cred["healthy_count"] or 0),
            "chain_entries": int(chain["chain_entries"] or 0),
            "ok": ok,
        })
    return {
        "data": result,
        "summary": {
            "total_categories": len(result),
            "configured": total_ok,
            "complete": total_ok == len(result),
        },
    }


# Probe-all

@router.post("/health/probe-all")
async def probe_all_credentials(
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    """Fan-out health check on all enabled credentials. Returns summary."""
    pool = await get_pool()
    creds = await pool.fetch(
        "SELECT id, category, provider_name, vault_path FROM provider_credentials WHERE enabled=TRUE"
    )
    results = []
    for row in creds:
        secret = get_secret_at(row["vault_path"], "api_key")
        ok, error, latency_ms = False, None, 0
        started = time.perf_counter()
        if not secret:
            error = "Secret missing"
        else:
            try:
                from src.providers.registry import ProviderRegistry
                cls = ProviderRegistry._registries.get(row["category"], {}).get(row["provider_name"])
                if cls is None:
                    error = "Provider not registered"
                else:
                    inst = cls()
                    hc = getattr(inst, "health_check", None)
                    if hc is None:
                        ok = True
                    else:
                        res = hc()
                        if hasattr(res, "__await__"):
                            import asyncio
                            res = await res
                        ok = bool(res)
            except Exception as exc:
                error = str(exc)
        latency_ms = int((time.perf_counter() - started) * 1000)
        await pool.execute(
            "UPDATE provider_credentials SET last_health_ok=$1, last_health_at=NOW(), last_latency_ms=$2 WHERE id=$3",
            ok, latency_ms, row["id"],
        )
        await pool.execute(
            "INSERT INTO provider_health_log (credential_id, ok, latency_ms, error) VALUES ($1,$2,$3,$4)",
            row["id"], ok, latency_ms, error,
        )
        results.append({"credential_id": row["id"], "provider_name": row["provider_name"],
                        "category": row["category"], "ok": ok, "latency_ms": latency_ms, "error": error})
    await audit(actor=actor, action="provider.probe_all",
                target_type="provider_credentials", target_id="all",
                after={"probed": len(results), "ok": sum(1 for r in results if r["ok"])},
                request=request)
    return {"data": results, "summary": {"total": len(results), "ok": sum(1 for r in results if r["ok"])}}


# Routing policies

class RouteIn(BaseModel):
    policy: str = "balanced"  # cheapest|fastest|highest_quality|balanced|custom
    custom_rules: dict = Field(default_factory=dict)
    primary_credential_id: int | None = None
    fallback_chain: list[int] = Field(default_factory=list)
    scope: str = "workspace"
    scope_id: str | None = None


@router.get("/routes")
async def list_routes(
    scope: str = "workspace",
    scope_id: str | None = None,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT r.id, r.scope, r.scope_id, r.category, r.policy,
                  r.custom_rules, r.primary_credential_id, r.fallback_chain,
                  r.enabled, r.updated_at,
                  c.label AS primary_label, c.provider_name AS primary_provider
             FROM provider_routes r
             LEFT JOIN provider_credentials c ON c.id = r.primary_credential_id
            WHERE r.scope=$1 AND ($2::text IS NULL OR r.scope_id=$2)
            ORDER BY r.category""",
        scope, scope_id,
    )
    return {"data": [dict(r) for r in rows]}


@router.put("/routes/{category}")
async def upsert_route(
    category: str,
    body: RouteIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id FROM provider_routes WHERE scope=$1 AND ($2::text IS NULL AND scope_id IS NULL OR scope_id=$2) AND category=$3",
        body.scope, body.scope_id, category,
    )
    if row:
        await pool.execute(
            """UPDATE provider_routes SET policy=$1, custom_rules=$2::jsonb,
               primary_credential_id=$3, fallback_chain=$4::bigint[],
               updated_at=NOW() WHERE id=$5""",
            body.policy, json.dumps(body.custom_rules),
            body.primary_credential_id, body.fallback_chain, row["id"],
        )
        rid = row["id"]
    else:
        rid = await pool.fetchval(
            """INSERT INTO provider_routes
                (scope, scope_id, category, policy, custom_rules, primary_credential_id, fallback_chain, created_by)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7::bigint[],$8) RETURNING id""",
            body.scope, body.scope_id, category, body.policy,
            json.dumps(body.custom_rules), body.primary_credential_id,
            body.fallback_chain, actor.user_id,
        )
    await audit(actor=actor, action="provider.route.upsert",
                target_type="provider_route", target_id=str(rid),
                after={"category": category, "policy": body.policy}, request=request)
    return {"status": "ok", "id": rid}


# Quotas

class QuotaIn(BaseModel):
    monthly_cap_usd: float
    alert_pct: int = 80
    hard_limit: bool = False
    scope: str = "workspace"
    scope_id: str | None = None
    category: str | None = None


@router.get("/quotas")
async def list_quotas(
    scope: str = "workspace",
    scope_id: str | None = None,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, scope, scope_id, category, monthly_cap_usd, current_spend,
                  period_start, alert_pct, hard_limit, updated_at
             FROM provider_quotas
            WHERE scope=$1 AND ($2::text IS NULL OR scope_id=$2)
            ORDER BY category NULLS FIRST""",
        scope, scope_id,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/quotas")
async def create_quota(
    body: QuotaIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    qid = await pool.fetchval(
        """INSERT INTO provider_quotas
            (scope, scope_id, category, monthly_cap_usd, alert_pct, hard_limit)
           VALUES ($1,$2,$3,$4,$5,$6)
           ON CONFLICT (scope, scope_id, category)
           DO UPDATE SET monthly_cap_usd=EXCLUDED.monthly_cap_usd,
                         alert_pct=EXCLUDED.alert_pct, hard_limit=EXCLUDED.hard_limit,
                         updated_at=NOW()
           RETURNING id""",
        body.scope, body.scope_id, body.category,
        body.monthly_cap_usd, body.alert_pct, body.hard_limit,
    )
    await audit(actor=actor, action="provider.quota.upsert",
                target_type="provider_quota", target_id=str(qid),
                after=body.model_dump(), request=request)
    return {"status": "ok", "id": qid}


@router.put("/quotas/{quota_id}")
async def update_quota(
    quota_id: int,
    body: QuotaIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    pool = await get_pool()
    res = await pool.execute(
        """UPDATE provider_quotas
              SET monthly_cap_usd=$1, alert_pct=$2, hard_limit=$3, updated_at=NOW()
            WHERE id=$4""",
        body.monthly_cap_usd, body.alert_pct, body.hard_limit, quota_id,
    )
    if res.endswith("0"):
        raise HTTPException(404, "Quota not found")
    await audit(actor=actor, action="provider.quota.update",
                target_type="provider_quota", target_id=str(quota_id),
                after=body.model_dump(), request=request)
    return {"status": "ok"}


# Sandbox runner

class SandboxRunIn(BaseModel):
    credential_id: int
    capability: str            # 'text-gen' | 'tts-standard' | 'image-gen'
    input_payload: dict = Field(default_factory=dict)
    # capability-specific convenience fields
    prompt: str | None = None  # for text-gen / image-gen
    text: str | None = None    # for tts


@router.post("/sandbox/run")
async def sandbox_run(
    body: SandboxRunIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin", "editor")),
):
    """Run a test inference against a specific credential and return the output."""
    pool = await get_pool()
    cred = await pool.fetchrow(
        "SELECT category, provider_name, vault_path, extra_config FROM provider_credentials WHERE id=$1",
        body.credential_id,
    )
    if not cred:
        raise HTTPException(404, "Credential not found")

    secret = get_secret_at(cred["vault_path"], "api_key")
    if not secret:
        raise HTTPException(400, "API key not found in vault — add credential first")

    started = time.perf_counter()
    ok: bool = False
    error: str | None = None
    output: dict = {}
    cost_usd = None

    try:
        from src.providers.registry import ProviderRegistry
        cls = ProviderRegistry._registries.get(cred["category"], {}).get(cred["provider_name"])
        if cls is None:
            raise ValueError(f"Provider {cred['provider_name']!r} not registered")
        inst = cls()

        if body.capability == "text-gen":
            prompt = body.prompt or body.input_payload.get("prompt", "Say hello in one sentence.")
            messages = [{"role": "user", "content": prompt}]
            fn = getattr(inst, "complete", None) or getattr(inst, "generate", None)
            if fn is None:
                raise ValueError("Provider has no complete() method")
            result = fn(messages=messages, max_tokens=200)
            if hasattr(result, "__await__"):
                import asyncio; result = await result
            text_out = result.get("content", str(result)) if isinstance(result, dict) else str(result)
            output = {"text": text_out}
            cost_usd = float(result.get("cost_usd", 0)) if isinstance(result, dict) else None
            ok = True

        elif body.capability in ("tts-standard", "tts-emotion"):
            text = body.text or body.input_payload.get("text", "Hello, this is a test.")
            fn = getattr(inst, "synthesize", None)
            if fn is None:
                raise ValueError("Provider has no synthesize() method")
            result = fn(text=text)
            if hasattr(result, "__await__"):
                import asyncio; result = await result
            output = {"audio_bytes_len": len(result) if isinstance(result, bytes) else 0,
                      "note": "Audio generated — preview via /library"}
            ok = True

        elif body.capability == "image-gen":
            prompt = body.prompt or body.input_payload.get("prompt", "A simple test image of a colorful sunset.")
            fn = getattr(inst, "generate_image", None) or getattr(inst, "generate", None)
            if fn is None:
                raise ValueError("Provider has no generate_image() method")
            result = fn(prompt=prompt)
            if hasattr(result, "__await__"):
                import asyncio; result = await result
            url = result.get("url", "") if isinstance(result, dict) else str(result)
            output = {"image_url": url}
            cost_usd = float(result.get("cost_usd", 0)) if isinstance(result, dict) else None
            ok = True

        else:
            # Generic: just run health_check
            hc = getattr(inst, "health_check", None)
            if hc:
                res = hc()
                if hasattr(res, "__await__"):
                    import asyncio; res = await res
                ok = bool(res)
            output = {"note": f"Capability {body.capability!r} — ran health_check as fallback"}

    except Exception as exc:
        error = str(exc)

    latency_ms = int((time.perf_counter() - started) * 1000)

    run_id = await pool.fetchval(
        """INSERT INTO provider_sandbox_runs
            (credential_id, run_by, capability, input_payload, output_payload, ok, latency_ms, cost_usd, error)
           VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6,$7,$8,$9) RETURNING id""",
        body.credential_id, actor.user_id, body.capability,
        json.dumps(body.input_payload or {"prompt": body.prompt, "text": body.text}),
        json.dumps(output), ok, latency_ms, cost_usd, error,
    )
    return {
        "status": "ok" if ok else "error",
        "data": {
            "run_id": run_id, "ok": ok, "latency_ms": latency_ms,
            "cost_usd": cost_usd, "output": output, "error": error,
        },
    }


@router.get("/sandbox/runs")
async def list_sandbox_runs(
    credential_id: int | None = None,
    limit: int = 20,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    if credential_id:
        rows = await pool.fetch(
            """SELECT id, credential_id, capability, ok, latency_ms, cost_usd, error, created_at
                 FROM provider_sandbox_runs WHERE credential_id=$1
                ORDER BY created_at DESC LIMIT $2""",
            credential_id, limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, credential_id, capability, ok, latency_ms, cost_usd, error, created_at
                 FROM provider_sandbox_runs ORDER BY created_at DESC LIMIT $1""",
            limit,
        )
    return {"data": [dict(r) for r in rows]}


# Enable / disable switches + admin clean-slate

class EnabledIn(BaseModel):
    enabled: bool


@router.put("/credentials/{credential_id}/enabled")
async def set_credential_enabled(
    credential_id: int,
    body: EnabledIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    """Master switch for a credential. Disabled credentials are skipped
    by the resolver across every scope/mode."""
    pool = await get_pool()
    cred = await pool.fetchrow(
        "SELECT category FROM provider_credentials WHERE id=$1", credential_id,
    )
    if not cred:
        raise HTTPException(404, "Credential not found")
    await pool.execute(
        "UPDATE provider_credentials SET enabled=$1, updated_at=NOW() WHERE id=$2",
        body.enabled, credential_id,
    )
    await audit(actor=actor, action="provider.credential.enabled",
                target_type="provider_credential", target_id=str(credential_id),
                after={"enabled": body.enabled}, request=request)
    await publish_invalidate(category=cred["category"])
    return {"status": "ok", "enabled": body.enabled}


@router.put("/chains/entry/{chain_entry_id}/enabled")
async def set_chain_entry_enabled(
    chain_entry_id: int,
    body: EnabledIn,
    request: Request,
    actor: Principal = Depends(require_role("owner", "admin")),
):
    """Per-chain-entry switch. Keeps position + ordering, but the
    resolver skips this entry while disabled."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT category, scope, scope_id, content_mode "
        "FROM provider_chains_v2 WHERE id=$1",
        chain_entry_id,
    )
    if not row:
        raise HTTPException(404, "Chain entry not found")
    await pool.execute(
        "UPDATE provider_chains_v2 SET is_enabled=$1 WHERE id=$2",
        body.enabled, chain_entry_id,
    )
    await audit(actor=actor, action="provider.chain_entry.enabled",
                target_type="provider_chain_v2_entry",
                target_id=str(chain_entry_id),
                after={"enabled": body.enabled}, request=request)
    await publish_invalidate(
        category=row["category"],
        channel_id=row["scope_id"] if row["scope"] == "channel" else None,
        content_mode=row["content_mode"],
    )
    return {"status": "ok", "enabled": body.enabled}


@router.post("/_admin/clean-slate")
async def admin_clean_slate(
    request: Request,
    actor: Principal = Depends(require_role("owner")),
):
    """Wipe ALL provider credentials, chains, routes, quotas, sandbox runs.

    Categories, content_modes, and feature flags are preserved. Used by
    the dashboard "Reset all providers" button and by the
    ``make providers-wipe`` CLI. Owner-only.
    """
    from src.providers.clean_slate import run as _run_wipe
    result = await _run_wipe(verbose=False)
    await audit(actor=actor, action="provider.clean_slate",
                target_type="providers", target_id="*",
                after=result, request=request)
    return {"status": "ok", "data": result}
