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


# ═══════════════════════════════════════════════════════════════════════════════
# Wave 2 — Marketplace, Routing, Quotas, Sandbox, Probe-all
# ═══════════════════════════════════════════════════════════════════════════════

# ── Marketplace ──────────────────────────────────────────────────────────────

@router.get("/marketplace")
async def list_marketplace(_: Principal = Depends(principal_dep)):
    """Return full provider catalog with `connected` flag for each entry."""
    pool = await get_pool()
    catalog = await pool.fetch(
        """SELECT id, provider_key, display_name, category, description,
                  logo_url, website_url, mode, capabilities, pricing_notes,
                  cost_unit, regions, has_free_tier, featured, sort_order
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


# ── Probe-all ────────────────────────────────────────────────────────────────

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


# ── Routing policies ─────────────────────────────────────────────────────────

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


# ── Quotas ───────────────────────────────────────────────────────────────────

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


# ── Sandbox runner ───────────────────────────────────────────────────────────

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
    ok, error, output: bool = False, None, {}
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
