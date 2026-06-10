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

import asyncio
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
    """Owner always allowed; Member allowed only when providers.admin_credentials.enabled is ON."""
    if p.role == "owner":
        return p
    if p.role == "member" and await flag_enabled("providers.admin_credentials.enabled"):
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


class KindIn(BaseModel):
    """Create a custom provider *section* (e.g. 'Avatar Generation')."""
    label: str
    kind: str | None = None          # slug; derived from label when omitted
    icon: str | None = None          # emoji
    description: str | None = None


class CategoryIn(BaseModel):
    """Create a custom *category* (slot) bound to a section."""
    label: str
    kind: str                        # section this category belongs to
    name: str | None = None          # slug; derived from label when omitted
    description: str | None = None


class MarketplaceProviderIn(BaseModel):
    """Add a custom provider to the marketplace under a section."""
    display_name: str
    kind: str                        # section the provider belongs to
    provider_key: str | None = None  # slug; derived from display_name when omitted
    description: str | None = None
    supported_models: list[str] = Field(default_factory=list)
    has_free_tier: bool = False
    cost_unit: str | None = None
    requires_api_key: bool = True


def _vault_path(category: str, provider_name: str, label: str) -> str:
    safe_label = "".join(c for c in label.lower() if c.isalnum() or c == "-") or "default"
    return f"providers/{category}/{provider_name}/{safe_label}"


def _as_json(value: Any, default: Any) -> Any:
    """Decode a JSONB column that asyncpg may return as a raw string.

    No JSONB type codec is registered on the pool (src/db.py), so JSONB
    columns come back as ``str`` from some drivers/paths and as parsed
    Python objects from others. The whole codebase assumes parsed objects
    for provider config; normalise here so callers (and the frontend) never
    receive a JSON string where they expect a list/dict. Returning a string
    to the UI is what caused ``config_schema.filter is not a function``.
    """
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default
    return value


def _slugify(text: str, *, sep: str = "_", maxlen: int = 40) -> str:
    """Lower-case, alnum + ``sep`` slug for category/provider/kind keys."""
    out: list[str] = []
    prev_sep = False
    for ch in text.strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_sep = False
        elif not prev_sep:
            out.append(sep)
            prev_sep = True
    slug = "".join(out).strip(sep)
    return slug[:maxlen] or "custom"


# Categories
@router.get("/categories")
async def list_categories(_: Principal = Depends(principal_dep)):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT name, label, kind, description, is_user_defined "
        "FROM provider_categories ORDER BY kind, name"
    )
    return {"data": [dict(r) for r in rows]}


# ── Sections (provider_kinds) ─────────────────────────────────────────────────
@router.get("/kinds")
async def list_kinds(_: Principal = Depends(principal_dep)):
    """List provider *sections* (LLM, Image, Avatar, …) with label + icon.

    Each row carries ``category_count`` so the UI can warn before deleting a
    section that still owns categories.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT k.kind, k.label, k.icon, k.description, k.is_user_defined, k.sort_order,
                  (SELECT COUNT(*) FROM provider_categories c WHERE c.kind = k.kind) AS category_count
             FROM provider_kinds k
            ORDER BY k.sort_order, k.label"""
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/kinds")
async def create_kind(
    body: KindIn,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Create a custom section. Also creates a default 'general' category under
    it so marketplace providers in this section have a category to reference."""
    pool = await get_pool()
    label = body.label.strip()
    if not label:
        raise HTTPException(422, "Section name is required")
    kind = _slugify(body.kind or label, maxlen=20)
    if not kind:
        raise HTTPException(422, "Could not derive a valid section key")
    existing = await pool.fetchrow("SELECT kind FROM provider_kinds WHERE kind=$1", kind)
    if existing:
        raise HTTPException(409, f"Section {kind!r} already exists")

    max_sort = await pool.fetchval("SELECT COALESCE(MAX(sort_order), 100) FROM provider_kinds")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO provider_kinds (kind, label, icon, description, is_user_defined, sort_order)
                   VALUES ($1,$2,$3,$4,TRUE,$5)""",
                kind, label, body.icon, body.description, int(max_sort) + 1,
            )
            # Default general category so providers can attach to this section.
            await conn.execute(
                """INSERT INTO provider_categories (name, label, kind, description, is_user_defined)
                   VALUES ($1,$2,$3,$4,TRUE)
                   ON CONFLICT (name) DO NOTHING""",
                kind, f"{label} (general)", kind, body.description,
            )
    await audit(actor=actor, action="provider.kind.create",
                target_type="provider_kind", target_id=kind,
                after={"label": label, "icon": body.icon}, request=request)
    return {"status": "ok", "kind": kind, "label": label}


@router.delete("/kinds/{kind}")
async def delete_kind(
    kind: str,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Delete a section and everything under it (categories, their credentials,
    chain entries, and catalog providers). Destructive — the UI guards this with
    a typed confirmation. Built-in sections can be recovered via Restore defaults."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT kind FROM provider_kinds WHERE kind=$1", kind)
    if not row:
        raise HTTPException(404, "Section not found")
    cat_names = [r["name"] for r in await pool.fetch(
        "SELECT name FROM provider_categories WHERE kind=$1", kind)]
    async with pool.acquire() as conn:
        async with conn.transaction():
            for cname in cat_names:
                await _purge_category(conn, cname)
            await conn.execute(
                "DELETE FROM provider_marketplace_catalog WHERE provider_key IN ("
                "  SELECT pmc.provider_key FROM provider_marketplace_catalog pmc "
                "  LEFT JOIN provider_categories c ON c.name = pmc.category "
                "  WHERE c.kind = $1 OR pmc.category = $1)",
                kind,
            )
            await conn.execute("DELETE FROM provider_kinds WHERE kind=$1", kind)
    await audit(actor=actor, action="provider.kind.delete",
                target_type="provider_kind", target_id=kind,
                after={"categories_removed": cat_names}, request=request)
    return {"status": "ok", "categories_removed": cat_names}


@router.post("/categories")
async def create_category(
    body: CategoryIn,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Create a custom category (slot) under an existing section."""
    pool = await get_pool()
    label = body.label.strip()
    if not label:
        raise HTTPException(422, "Category name is required")
    kind = _slugify(body.kind, maxlen=20)
    sec = await pool.fetchrow("SELECT kind FROM provider_kinds WHERE kind=$1", kind)
    if not sec:
        raise HTTPException(400, f"Unknown section {kind!r}. Create the section first.")
    name = _slugify(body.name or f"{kind}_{label}", maxlen=40)
    existing = await pool.fetchrow("SELECT name FROM provider_categories WHERE name=$1", name)
    if existing:
        raise HTTPException(409, f"Category {name!r} already exists")
    await pool.execute(
        """INSERT INTO provider_categories (name, label, kind, description, is_user_defined)
           VALUES ($1,$2,$3,$4,TRUE)""",
        name, label, kind, body.description,
    )
    await audit(actor=actor, action="provider.category.create",
                target_type="provider_category", target_id=name,
                after={"label": label, "kind": kind}, request=request)
    return {"status": "ok", "name": name, "label": label, "kind": kind}


@router.patch("/categories/{name}")
async def rename_category(
    name: str,
    body: dict,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Rename a category's display label. The internal name (slug) is immutable."""
    pool = await get_pool()
    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(422, "label is required")
    row = await pool.fetchrow("SELECT name FROM provider_categories WHERE name=$1", name)
    if not row:
        raise HTTPException(404, "Category not found")
    await pool.execute(
        "UPDATE provider_categories SET label=$1 WHERE name=$2", label, name
    )
    await audit(actor=actor, action="provider.category.rename",
                target_type="provider_category", target_id=name,
                after={"label": label}, request=request)
    return {"status": "ok", "name": name, "label": label}


@router.delete("/categories/{name}")
async def delete_category(
    name: str,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Delete a category and its credentials + chain entries. Destructive."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT name FROM provider_categories WHERE name=$1", name)
    if not row:
        raise HTTPException(404, "Category not found")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _purge_category(conn, name)
    await audit(actor=actor, action="provider.category.delete",
                target_type="provider_category", target_id=name, request=request)
    await publish_invalidate(category=name)
    return {"status": "ok"}


async def _purge_category(conn: Any, name: str) -> None:
    """Remove a category plus its dependent rows, in FK-safe order.

    Credentials reference the category and are themselves referenced by chains
    and routes, so dependents are deleted first. The secrets backend has no
    delete API; vault entries become orphaned references, which are harmless.
    """
    await conn.execute("DELETE FROM provider_chains_v2 WHERE category=$1", name)
    await conn.execute("DELETE FROM provider_priority_chains WHERE category=$1", name)
    await conn.execute("DELETE FROM provider_routes WHERE category=$1", name)
    await conn.execute("DELETE FROM provider_credentials WHERE category=$1", name)
    await conn.execute(
        "DELETE FROM provider_marketplace_catalog WHERE category=$1", name)
    await conn.execute("DELETE FROM provider_categories WHERE name=$1", name)


@router.post("/restore-defaults")
async def restore_defaults(
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Recreate the built-in sections + categories after accidental deletion.

    Does not restore deleted credentials (secrets are gone) or re-seed every
    marketplace provider — only the taxonomy needed to keep the pipeline wired.
    """
    pool = await get_pool()
    await pool.execute("SELECT seed_builtin_provider_taxonomy()")
    await audit(actor=actor, action="provider.taxonomy.restore_defaults",
                target_type="provider_taxonomy", target_id="builtin", request=request)
    return {"status": "ok"}


# Credentials
@router.get("/credentials")
async def list_credentials(
    category: str | None = None,
    channel_id: str | None = Query(None),
    content_mode: str | None = Query(None),
    actor: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    filters = []
    args: list[Any] = []
    # Scope: show credentials belonging to this workspace OR system defaults (NULL).
    # Superadmin/legacy sessions see all credentials across all workspaces.
    if actor.global_role != "superadmin" and actor.source != "legacy":
        args.append(actor.workspace_id)
        filters.append(f"(workspace_id=${len(args)} OR workspace_id IS NULL)")
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
                  workspace_id, enabled, last_health_ok, last_health_at, last_latency_ms,
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
            # Not a built-in Python class — accept it only if it exists in the
            # marketplace catalog (a user-added "catalog-only" provider). Such a
            # credential is stored and shown as connected, but the runtime can't
            # call it until an adapter class ships (is_callable=FALSE).
            in_catalog = await pool.fetchval(
                "SELECT 1 FROM provider_marketplace_catalog WHERE provider_key=$1",
                body.provider_name,
            )
            if not in_catalog:
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
             channel_id, content_mode, scope_priority, enabled, created_by, workspace_id)
           VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,TRUE,$10,$11) RETURNING id""",
        body.category, body.provider_name, body.label, path,
        json.dumps(body.extra_config), body.model,
        body.channel_id, body.content_mode, scope_priority, actor.user_id,
        actor.workspace_id,
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

    schema: list[dict] = _as_json(catalog_row["config_schema"], [])

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

    # Workspace ownership check — fetch existing credential first so we can
    # verify it belongs to this workspace before patching.
    _ws_check = await pool.fetchrow(
        "SELECT category, provider_name, workspace_id FROM provider_credentials WHERE id=$1",
        credential_id,
    )
    if not _ws_check:
        raise HTTPException(404, "Credential not found")
    if (
        actor.global_role != "superadmin" and actor.source != "legacy"
        and _ws_check["workspace_id"] is not None
        and _ws_check["workspace_id"] != actor.workspace_id
    ):
        raise HTTPException(403, "Credential belongs to a different workspace")

    if "model" in updates and updates["model"]:
        _validate_model(_ws_check["category"], _ws_check["provider_name"], updates["model"])

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
        "SELECT category, workspace_id FROM provider_credentials WHERE id=$1", credential_id,
    )
    if not cat_row:
        raise HTTPException(404, "Credential not found")
    if (
        actor.global_role != "superadmin" and actor.source != "legacy"
        and cat_row["workspace_id"] is not None
        and cat_row["workspace_id"] != actor.workspace_id
    ):
        raise HTTPException(403, "Credential belongs to a different workspace")
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
    actor: Principal = Depends(require_role("owner", "member")),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT category, provider_name, vault_path, extra_config, workspace_id "
        "FROM provider_credentials WHERE id=$1",
        credential_id,
    )
    if not row:
        raise HTTPException(404, "Credential not found")
    if (
        actor.global_role != "superadmin" and actor.source != "legacy"
        and row["workspace_id"] is not None
        and row["workspace_id"] != actor.workspace_id
    ):
        raise HTTPException(403, "Credential belongs to a different workspace")

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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
        "SELECT provider_key, display_name, logo_url, website_url, has_free_tier, "
        "       config_schema, docs_url, pricing_tier "
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
            "config_schema": _as_json(cat_entry.get("config_schema"), []),
            "docs_url": cat_entry.get("docs_url"),
            "pricing_tier": cat_entry.get("pricing_tier"),
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
        d["config_schema"] = _as_json(d.get("config_schema"), [])
        d["supported_models"] = _as_json(d.get("supported_models"), [])
        result.append(d)
    return {"data": result}


def _default_config_schema(requires_api_key: bool) -> list[dict]:
    """Minimal schema for a user-added provider: optional API key + model.

    Kept deliberately simple so a non-technical creator only sees a key field
    and a model field. The key is stored in Vault; the model goes to extra_config.
    """
    fields: list[dict] = []
    if requires_api_key:
        fields.append({
            "name": "api_key", "type": "password", "label": "API Key",
            "required": True, "hint": "Paste the API key from your provider's dashboard.",
        })
    fields.append({
        "name": "model", "type": "text", "label": "Model (optional)",
        "required": False, "placeholder": "e.g. avatar-v3",
    })
    return fields


@router.post("/marketplace")
async def create_marketplace_provider(
    body: MarketplaceProviderIn,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Add a custom provider card to the marketplace under a section.

    Stored as catalog-only (``is_callable=FALSE``): selectable and connectable,
    but the runtime can't call it until an adapter class ships. The catalog row
    references the section's general category so it groups with the section.
    """
    pool = await get_pool()
    display_name = body.display_name.strip()
    if not display_name:
        raise HTTPException(422, "Provider name is required")
    kind = _slugify(body.kind, maxlen=20)
    sec = await pool.fetchrow("SELECT kind FROM provider_kinds WHERE kind=$1", kind)
    if not sec:
        raise HTTPException(400, f"Unknown section {kind!r}. Create the section first.")
    # Catalog rows reference a category name; use this section's general category
    # (created alongside the section, name == kind). Fall back to any category in
    # the section if the general one was renamed/removed.
    cat = await pool.fetchrow(
        "SELECT name FROM provider_categories WHERE name=$1", kind
    ) or await pool.fetchrow(
        "SELECT name FROM provider_categories WHERE kind=$1 ORDER BY name LIMIT 1", kind
    )
    if not cat:
        raise HTTPException(400, f"Section {kind!r} has no category to attach the provider to.")
    provider_key = _slugify(body.provider_key or display_name, maxlen=60)
    existing = await pool.fetchrow(
        "SELECT provider_key FROM provider_marketplace_catalog WHERE provider_key=$1", provider_key)
    if existing:
        raise HTTPException(409, f"Provider {provider_key!r} already exists")
    await pool.execute(
        """INSERT INTO provider_marketplace_catalog
              (provider_key, display_name, category, description, mode, capabilities,
               cost_unit, has_free_tier, featured, sort_order,
               config_schema, supported_models, is_platform_seeded, pricing_tier,
               is_user_defined, is_callable)
           VALUES ($1,$2,$3,$4,'byok',ARRAY[]::text[],$5,$6,FALSE,90,
                   $7::jsonb,$8::jsonb,FALSE,$9,TRUE,FALSE)""",
        provider_key, display_name, cat["name"], body.description,
        body.cost_unit, body.has_free_tier,
        json.dumps(_default_config_schema(body.requires_api_key)),
        json.dumps(body.supported_models or []),
        "free" if body.has_free_tier else "paid",
    )
    await audit(actor=actor, action="provider.marketplace.create",
                target_type="provider_marketplace", target_id=provider_key,
                after={"display_name": display_name, "kind": kind}, request=request)
    return {"status": "ok", "provider_key": provider_key, "category": cat["name"]}


@router.delete("/marketplace/{provider_key}")
async def delete_marketplace_provider(
    provider_key: str,
    request: Request,
    actor: Principal = Depends(_require_cred_actor),
):
    """Remove a marketplace provider. Existing credentials that used it are left
    intact (they still resolve by provider_name) but it disappears from the
    'add provider' lists."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT provider_key FROM provider_marketplace_catalog WHERE provider_key=$1", provider_key)
    if not row:
        raise HTTPException(404, "Provider not found")
    await pool.execute(
        "DELETE FROM provider_marketplace_catalog WHERE provider_key=$1", provider_key)
    await audit(actor=actor, action="provider.marketplace.delete",
                target_type="provider_marketplace", target_id=provider_key, request=request)
    return {"status": "ok"}


@router.get("/catalog-for-category")
async def catalog_for_category(
    category: str,
    _: Principal = Depends(principal_dep),
):
    """Marketplace providers available to a category — i.e. every catalog entry
    in the same section (kind). Powers the 'Configure category' picker so a user
    sees exactly the providers belonging to that section (built-in + custom)."""
    pool = await get_pool()
    cat = await pool.fetchrow("SELECT kind FROM provider_categories WHERE name=$1", category)
    if not cat:
        raise HTTPException(404, f"Unknown category {category!r}")
    rows = await pool.fetch(
        """SELECT pmc.provider_key, pmc.display_name, pmc.description, pmc.logo_url,
                  pmc.has_free_tier, pmc.cost_unit, pmc.config_schema, pmc.supported_models,
                  pmc.docs_url, pmc.pricing_tier, pmc.is_user_defined, pmc.is_callable
             FROM provider_marketplace_catalog pmc
             JOIN provider_categories pc ON pc.name = pmc.category
            WHERE pc.kind = $1
            ORDER BY pmc.is_user_defined, pmc.sort_order, pmc.display_name""",
        cat["kind"],
    )
    out = []
    for r in rows:
        d = dict(r)
        d["config_schema"] = _as_json(d.get("config_schema"), [])
        d["supported_models"] = _as_json(d.get("supported_models"), [])
        out.append(d)
    return {"data": out, "kind": cat["kind"]}


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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
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
    actor: Principal = Depends(require_role("owner", "member")),
):
    """Master switch for a credential. Disabled credentials are skipped
    by the resolver across every scope/mode."""
    pool = await get_pool()
    cred = await pool.fetchrow(
        "SELECT category, workspace_id FROM provider_credentials WHERE id=$1", credential_id,
    )
    if not cred:
        raise HTTPException(404, "Credential not found")
    if (
        actor.global_role != "superadmin" and actor.source != "legacy"
        and cred["workspace_id"] is not None
        and cred["workspace_id"] != actor.workspace_id
    ):
        raise HTTPException(403, "Credential belongs to a different workspace")
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
    actor: Principal = Depends(require_role("owner", "member")),
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


@router.get("/health-stream")
async def health_stream(
    category: str | None = Query(default=None, description="Filter events to a specific provider category"),
    actor: Principal = Depends(principal_dep),
):
    """Server-Sent Events endpoint — streams real-time provider health changes.

    The frontend subscribes via ``EventSource``. Each time a credential's
    health status changes (detected by the Temporal health beat every 5 min),
    this endpoint emits a ``health_change`` SSE event.

    A ``heartbeat`` comment is emitted every 25 s to keep proxies alive.
    """
    from fastapi.responses import StreamingResponse
    from src.workers.provider_health_beat import HEALTH_PUBSUB_CHANNEL

    async def _event_generator():  # type: ignore[return]
        try:
            from src.redis_client import get_redis
            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(HEALTH_PUBSUB_CHANNEL)
            while True:
                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=25),
                        timeout=30,
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if msg and msg.get("type") == "message":
                    raw = msg.get("data", "")
                    if category:
                        try:
                            parsed = json.loads(raw)
                            if parsed.get("category") != category:
                                continue
                        except Exception:
                            pass
                    yield f"event: health_change\ndata: {raw}\n\n"
                else:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            try:
                await pubsub.unsubscribe(HEALTH_PUBSUB_CHANNEL)
                await pubsub.aclose()
            except Exception:  # noqa: BLE001
                pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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
