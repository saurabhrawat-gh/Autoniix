"""Asset & music library — read-only browse over the asset_library and
brand_assets tables, plus the MinIO ``music/`` prefix.

Endpoints
---------
GET /library/assets        Stock-asset cache rows (asset_library)
GET /library/brand         Per-channel brand assets (brand_assets)
GET /library/music         Music tracks in MinIO (best-effort)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.db import get_pool

from ._deps import Principal, principal_dep

router = APIRouter()


@router.get("/assets")
async def list_assets(
    q: str | None = Query(None),
    provider: str | None = Query(None),
    limit: int = Query(60, ge=1, le=300),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    where = ["1=1"]
    args: list = []
    if q:
        args.append(f"%{q.lower()}%")
        where.append(f"LOWER(query_text) LIKE ${len(args)}")
    if provider:
        args.append(provider)
        where.append(f"provider = ${len(args)}")
    args.append(limit)
    rows = await pool.fetch(
        f"""
        SELECT id, query_text, provider, asset_url, thumbnail_url,
               width, height, duration_seconds, quality_score, created_at
          FROM asset_library
         WHERE {" AND ".join(where)}
         ORDER BY quality_score DESC NULLS LAST, created_at DESC
         LIMIT ${len(args)}
        """,
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.get("/brand")
async def list_brand_assets(
    channel_id: str | None = Query(None),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    if channel_id:
        rows = await pool.fetch(
            """SELECT id, channel_id, asset_type, asset_url, metadata, created_at
                 FROM brand_assets WHERE channel_id = $1 ORDER BY created_at DESC""",
            channel_id,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, channel_id, asset_type, asset_url, metadata, created_at
                 FROM brand_assets ORDER BY created_at DESC LIMIT 200"""
        )
    return {"data": [dict(r) for r in rows]}


@router.get("/music")
async def list_music(_: Principal = Depends(principal_dep)):
    """List music objects under the ``music/`` MinIO prefix."""
    out: list[dict] = []
    try:
        from src.providers.registry import ProviderRegistry
        storage = ProviderRegistry.get("storage")
        client = getattr(storage, "client", None)
        bucket = getattr(storage, "bucket", None)
        if client and bucket:
            for obj in client.list_objects(bucket, prefix="music/", recursive=True):
                out.append({
                    "key": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                })
    except Exception:
        pass
    return {"data": out}
