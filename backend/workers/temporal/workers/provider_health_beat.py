"""AE-75 — Provider Health Beat: Temporal activity + workflow.

Runs every 5 minutes via the ``provider-health-beat`` Temporal schedule
(registered in ``scripts/register_schedules.py``).

For each enabled credential:
  1. Calls the provider's ``health_check()`` method.
  2. Writes ``last_health_ok`` + ``last_health_at`` to ``provider_credentials``.
  3. Inserts a row into ``provider_health_log``.
  4. On status change (ok→fail or fail→ok), publishes to the
     ``provider:health:changed`` Redis pub/sub channel so the SSE
     endpoint fans out to connected dashboard clients.
  5. Emits Prometheus metrics: unhealthy counter + latency histogram.

The per-credential health-check logic is identical to the one used by
``POST /credentials/{id}/test``; kept in :func:`_run_one_credential_check`
so both code paths stay in sync.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import structlog

    from core.db import get_pool
    from providers.secrets import get_secret_at

logger = structlog.get_logger()

HEALTH_PUBSUB_CHANNEL = "provider:health:changed"


async def publish_health_change(
    credential_id: int,
    category: str,
    provider_name: str,
    ok: bool,
) -> None:
    """Publish a health-status-change event to Redis (best-effort)."""
    try:
        from core.redis_client import get_redis

        redis = await get_redis()
        payload = json.dumps(
            {
                "credential_id": credential_id,
                "category": category,
                "provider_name": provider_name,
                "ok": ok,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        await redis.publish(HEALTH_PUBSUB_CHANNEL, payload)
        logger.debug(
            "provider.health.published",
            credential_id=credential_id,
            category=category,
            ok=ok,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("provider.health.publish_failed", error=str(exc))


async def _run_one_credential_check(
    credential_id: int,
    category: str,
    provider_name: str,
    vault_path: str,
    extra_config: dict[str, Any] | None,
) -> tuple[bool, str | None, int]:
    """Run a single health check and return (ok, error, latency_ms)."""
    from observability.metrics import PROVIDER_HEALTH_CHECK_DURATION
    from providers.registry import ProviderRegistry

    secret = get_secret_at(vault_path, "api_key")
    started = time.perf_counter()
    ok, error = False, None

    if not secret:
        error = "Secret not found in vault"
    else:
        try:
            cls = ProviderRegistry._registries.get(category, {}).get(provider_name)
            if cls is None:
                error = f"Provider {provider_name!r} not registered"
            else:
                inst = cls()
                hc = getattr(inst, "health_check", None)
                if hc is None:
                    ok = True
                else:
                    res = hc()
                    if hasattr(res, "__await__"):
                        res = await res  # type: ignore[assignment]
                    ok = bool(res)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

    latency_ms = int((time.perf_counter() - started) * 1000)
    PROVIDER_HEALTH_CHECK_DURATION.labels(provider_name=provider_name).observe(latency_ms)
    return ok, error, latency_ms


@activity.defn
async def check_all_provider_health() -> dict[str, Any]:
    """Temporal activity: health-check all enabled credentials.

    Returns a summary dict: {credential_id: ok, ...}.
    """
    from observability.metrics import PROVIDER_HEALTH_UNHEALTHY

    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, category, provider_name, vault_path, extra_config FROM provider_credentials WHERE enabled = TRUE"
    )

    results: dict[str, bool] = {}
    changed: list[dict[str, Any]] = []

    for row in rows:
        cred_id: int = row["id"]
        category: str = row["category"]
        provider_name: str = row["provider_name"]

        ok, error, latency_ms = await _run_one_credential_check(
            credential_id=cred_id,
            category=category,
            provider_name=provider_name,
            vault_path=row["vault_path"],
            extra_config=dict(row["extra_config"]) if row["extra_config"] else {},
        )

        results[str(cred_id)] = ok

        if not ok:
            PROVIDER_HEALTH_UNHEALTHY.labels(category=category).inc()

        prev_ok = await pool.fetchval("SELECT last_health_ok FROM provider_credentials WHERE id=$1", cred_id)

        await pool.execute(
            """UPDATE provider_credentials
                  SET last_health_ok=$1, last_health_at=NOW(), last_latency_ms=$2
                WHERE id=$3""",
            ok,
            latency_ms,
            cred_id,
        )
        await pool.execute(
            """INSERT INTO provider_health_log (credential_id, ok, latency_ms, error)
               VALUES ($1,$2,$3,$4)""",
            cred_id,
            ok,
            latency_ms,
            error,
        )

        if prev_ok != ok:
            changed.append(
                {
                    "credential_id": cred_id,
                    "category": category,
                    "provider_name": provider_name,
                    "ok": ok,
                }
            )
            logger.info(
                "provider.health.status_changed",
                credential_id=cred_id,
                category=category,
                prev=prev_ok,
                now=ok,
            )

    if changed:
        await asyncio.gather(
            *(
                publish_health_change(
                    credential_id=c["credential_id"],
                    category=c["category"],
                    provider_name=c["provider_name"],
                    ok=c["ok"],
                )
                for c in changed
            ),
            return_exceptions=True,
        )

    total = len(rows)
    healthy = sum(1 for v in results.values() if v)
    logger.info(
        "provider.health.beat.complete",
        total=total,
        healthy=healthy,
        unhealthy=total - healthy,
        changed=len(changed),
    )
    return {"total": total, "healthy": healthy, "unhealthy": total - healthy, "results": results}
