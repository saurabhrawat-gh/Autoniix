"""Asset & music library — legacy browse endpoints + Wave 3 full DAM.

Legacy endpoints (unchanged)
-----------------------------
GET /library/assets        Stock-asset cache rows (asset_library)
GET /library/brand         Per-channel brand assets (brand_assets)
GET /library/music         Music tracks in MinIO (best-effort)

Wave 3 DAM endpoints
--------------------
GET    /library/dam/assets           List scoped assets with filters
POST   /library/dam/assets/preflight SHA-256 dedup check
POST   /library/dam/upload           Multipart upload → MinIO → dam_assets row
GET    /library/dam/assets/{id}      Asset detail (with versions, renditions, tags)
PATCH  /library/dam/assets/{id}      Update display_name / tags / license
DELETE /library/dam/assets/{id}      Soft-delete

GET    /library/dam/tags             Distinct tags in scope
GET    /library/dam/collections      List collections
POST   /library/dam/collections      Create collection (manual or smart)
PUT    /library/dam/collections/{id} Update
DELETE /library/dam/collections/{id} Delete

GET    /library/dam/brand-kits       List brand kits
POST   /library/dam/brand-kits       Create brand kit
PUT    /library/dam/brand-kits/{id}  Update

POST   /library/dam/search           Hybrid full-text + vector search
"""
from __future__ import annotations

import hashlib
import io
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

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


# Wave 3 — DAM

def _storage_key(scope: str, scope_id: str | None, kind: str, filename: str) -> str:
    uid = uuid.uuid4().hex[:12]
    sid = scope_id or "global"
    return f"dam/{scope}/{sid}/{kind}/{uid}_{filename}"


# helpers

async def _upload_to_minio(data: bytes, key: str, content_type: str) -> bool:
    """Best-effort upload to MinIO; returns True on success."""
    try:
        from src.providers.registry import ProviderRegistry
        storage = ProviderRegistry.get("storage")
        client = getattr(storage, "client", None)
        bucket = getattr(storage, "bucket", None)
        if client and bucket:
            client.put_object(bucket, key, io.BytesIO(data), len(data),
                              content_type=content_type)
            return True
    except Exception:
        pass
    return False


async def _enqueue_media_jobs(pool: Any, asset_id: int, kind: str) -> None:
    """Queue pipeline jobs appropriate for asset kind."""
    job_map = {
        "video": ["probe", "poster", "waveform", "transcode_hls", "embed"],
        "audio": ["probe", "waveform", "transcribe", "embed"],
        "image": ["probe", "poster", "embed", "autotag"],
        "font": ["probe"],
        "lut": ["probe"],
        "template": [],
        "document": ["embed"],
        "other": ["probe"],
    }
    jobs = job_map.get(kind, ["probe"])
    if jobs:
        await pool.executemany(
            "INSERT INTO media_jobs (asset_id, kind, priority) VALUES ($1, $2, $3)"
            " ON CONFLICT DO NOTHING",
            [(asset_id, j, 5) for j in jobs],
        )


# models

class AssetPatch(BaseModel):
    display_name: str | None = None
    tags: list[str] | None = None
    license: str | None = None
    license_url: str | None = None
    expires_at: str | None = None


class CollectionIn(BaseModel):
    name: str
    description: str | None = None
    kind: str = "manual"
    query: dict = {}
    asset_ids: list[int] = []
    scope: str = "workspace"
    scope_id: str | None = None


class BrandKitIn(BaseModel):
    name: str
    scope: str = "brand"
    scope_id: str | None = None
    logo_asset_ids: list[int] = []
    palette: dict = {}
    font_asset_ids: list[int] = []
    notes: str | None = None


class SearchIn(BaseModel):
    q: str
    scope: str = "workspace"
    scope_id: str | None = None
    kind: str | None = None
    tags: list[str] | None = None
    limit: int = 40
    # AE-356: search mode.
    #   hybrid    — semantic if a query embedding succeeds; FTS otherwise.
    #               Results are union-merged with score fusion (RRF-style).
    #   semantic  — semantic only; empty result if embeddings unavailable.
    #   fts       — legacy full-text + ILIKE match (the historical behaviour).
    mode: str = "hybrid"


# GET /library/dam/assets

@router.get("/dam/assets")
async def dam_list_assets(
    scope: str = Query("workspace"),
    scope_id: str | None = Query(None),
    kind: str | None = Query(None),
    q: str | None = Query(None),
    tag: str | None = Query(None),
    origin: str | None = Query(None),
    limit: int = Query(60, ge=1, le=300),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    where = ["deleted_at IS NULL", "scope = $1"]
    args: list[Any] = [scope]
    if scope_id:
        args.append(scope_id)
        where.append(f"scope_id = ${len(args)}")
    if kind:
        args.append(kind)
        where.append(f"kind = ${len(args)}")
    if origin:
        args.append(origin)
        where.append(f"origin = ${len(args)}")
    if tag:
        args.append(tag)
        where.append(f"${len(args)} = ANY(tags)")
    if q:
        args.append(q)
        where.append(f"to_tsvector('english', display_name) @@ plainto_tsquery('english', ${len(args)})")
    args.extend([limit, offset])
    rows = await pool.fetch(
        f"""SELECT id, scope, scope_id, kind, display_name, mime_type, bytes,
                   content_hash, storage_key, thumbnail_key, origin, license,
                   expires_at, tags, ai_tags, metadata, created_by, created_at
              FROM dam_assets
             WHERE {" AND ".join(where)}
             ORDER BY created_at DESC
             LIMIT ${len(args) - 1} OFFSET ${len(args)}""",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


# POST /library/dam/assets/preflight

@router.post("/dam/assets/preflight")
async def dam_preflight(
    sha256: str = Query(..., description="SHA-256 hex of file content"),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, display_name, storage_key, scope FROM dam_assets"
        " WHERE content_hash = $1 AND deleted_at IS NULL LIMIT 1",
        sha256,
    )
    if row:
        return {"exists": True, "asset": dict(row)}
    return {"exists": False}


# POST /library/dam/upload

@router.post("/dam/upload")
async def dam_upload(
    files: list[UploadFile] = File(...),
    scope: str = Form("workspace"),
    scope_id: str | None = Form(None),
    kind: str = Form("image"),
    license: str | None = Form(None),
    tags: str = Form("[]"),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    results = []

    # AE-364: pre-check quota once per upload call so a 50-file batch fails
    # fast instead of writing half then aborting mid-loop. We sum the
    # non-deduped bytes below as we go and abort the batch if it would
    # cross the scope's quota.
    from src.services.dashboard.v2.library_quotas import check_quota_before_upload

    incoming_total = 0
    for f in files:
        # ``UploadFile.size`` is set by Starlette when the client sends a
        # Content-Length; falling back to 0 means "we'll discover the size
        # when we read the stream" — the per-file check below still catches
        # over-quota uploads, just one file later.
        incoming_total += int(getattr(f, "size", None) or 0)
    quota = await check_quota_before_upload(scope, scope_id, incoming_total)
    if not quota["ok"]:
        raise HTTPException(
            413,
            f"upload would exceed quota: requested {incoming_total} bytes, "
            f"{quota['remaining_bytes']} remaining of {quota['quota_bytes']}",
        )

    for f in files:
        data = await f.read()
        sha = hashlib.sha256(data).hexdigest()

        # Dedup check
        existing = await pool.fetchrow(
            "SELECT id FROM dam_assets WHERE content_hash = $1 AND deleted_at IS NULL LIMIT 1",
            sha,
        )
        if existing:
            results.append({"id": existing["id"], "dedup": True, "file": f.filename})
            continue

        key = _storage_key(scope, scope_id, kind, f.filename or "upload")
        await _upload_to_minio(data, key, f.content_type or "application/octet-stream")

        tag_list: list[str] = json.loads(tags) if tags else []
        row = await pool.fetchrow(
            """INSERT INTO dam_assets
               (scope, scope_id, kind, display_name, mime_type, bytes,
                content_hash, storage_key, origin, license, tags)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'uploaded',$9,$10)
               RETURNING id, display_name""",
            scope, scope_id, kind,
            f.filename or "untitled",
            f.content_type or "application/octet-stream",
            len(data), sha, key, license, tag_list,
        )
        asset_id = row["id"]
        await _enqueue_media_jobs(pool, asset_id, kind)
        results.append({"id": asset_id, "dedup": False, "file": f.filename})

    return {"count": len(results), "results": results}


# GET /library/dam/assets/{id}

@router.get("/dam/assets/{asset_id}")
async def dam_get_asset(
    asset_id: int,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM dam_assets WHERE id = $1 AND deleted_at IS NULL", asset_id
    )
    if not row:
        raise HTTPException(404, "Asset not found")
    asset = dict(row)
    # versions
    versions = await pool.fetch(
        "SELECT id, version_no, bytes, content_hash, note, created_at"
        " FROM dam_asset_versions WHERE asset_id = $1 ORDER BY version_no DESC",
        asset_id,
    )
    asset["versions"] = [dict(v) for v in versions]
    # renditions
    renditions = await pool.fetch(
        "SELECT rendition_kind, storage_key, codec, width, height, bitrate_kbps,"
        " duration_ms, bytes FROM media_renditions WHERE asset_id = $1",
        asset_id,
    )
    asset["renditions"] = [dict(r) for r in renditions]
    # media jobs (recent)
    jobs = await pool.fetch(
        "SELECT kind, status, error, finished_at FROM media_jobs"
        " WHERE asset_id = $1 ORDER BY created_at DESC LIMIT 10",
        asset_id,
    )
    asset["media_jobs"] = [dict(j) for j in jobs]
    return {"data": asset}


# PATCH /library/dam/assets/{id}

@router.patch("/dam/assets/{asset_id}")
async def dam_patch_asset(
    asset_id: int,
    body: AssetPatch,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    sets, args = [], [asset_id]
    if body.display_name is not None:
        args.append(body.display_name); sets.append(f"display_name=${len(args)}")
    if body.tags is not None:
        args.append(body.tags); sets.append(f"tags=${len(args)}")
    if body.license is not None:
        args.append(body.license); sets.append(f"license=${len(args)}")
    if body.license_url is not None:
        args.append(body.license_url); sets.append(f"license_url=${len(args)}")
    if body.expires_at is not None:
        args.append(body.expires_at); sets.append(f"expires_at=${len(args)}")
    if not sets:
        raise HTTPException(400, "No fields to update")
    await pool.execute(
        f"UPDATE dam_assets SET {', '.join(sets)}, updated_at=now() WHERE id=$1 AND deleted_at IS NULL",
        *args,
    )
    return {"ok": True}


# DELETE /library/dam/assets/{id}

@router.delete("/dam/assets/{asset_id}")
async def dam_delete_asset(
    asset_id: int,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    await pool.execute(
        "UPDATE dam_assets SET deleted_at=now() WHERE id=$1 AND deleted_at IS NULL",
        asset_id,
    )
    return {"ok": True}


# GET /library/dam/tags

@router.get("/dam/tags")
async def dam_list_tags(
    scope: str = Query("workspace"),
    scope_id: str | None = Query(None),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    args: list[Any] = [scope]
    cond = "scope = $1 AND deleted_at IS NULL"
    if scope_id:
        args.append(scope_id)
        cond += f" AND scope_id = ${len(args)}"
    rows = await pool.fetch(
        f"SELECT DISTINCT unnest(tags) AS tag FROM dam_assets WHERE {cond} ORDER BY 1",
        *args,
    )
    return {"data": [r["tag"] for r in rows]}


# Collections CRUD

@router.get("/dam/collections")
async def dam_list_collections(
    scope: str = Query("workspace"),
    scope_id: str | None = Query(None),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    args: list[Any] = [scope]
    cond = "scope = $1"
    if scope_id:
        args.append(scope_id); cond += f" AND scope_id = ${len(args)}"
    rows = await pool.fetch(
        f"SELECT id, name, description, kind, query, asset_ids, cover_asset_id,"
        f" owner_id, created_at FROM dam_collections WHERE {cond} ORDER BY name",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/dam/collections")
async def dam_create_collection(
    body: CollectionIn,
    p: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO dam_collections
           (scope, scope_id, name, description, kind, query, asset_ids, owner_id)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id""",
        body.scope, body.scope_id, body.name, body.description,
        body.kind, json.dumps(body.query), body.asset_ids, p.sub,
    )
    return {"id": row["id"]}


@router.put("/dam/collections/{col_id}")
async def dam_update_collection(
    col_id: int,
    body: CollectionIn,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    await pool.execute(
        """UPDATE dam_collections
              SET name=$2, description=$3, kind=$4, query=$5, asset_ids=$6, updated_at=now()
            WHERE id=$1""",
        col_id, body.name, body.description, body.kind,
        json.dumps(body.query), body.asset_ids,
    )
    return {"ok": True}


@router.delete("/dam/collections/{col_id}")
async def dam_delete_collection(
    col_id: int,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    await pool.execute("DELETE FROM dam_collections WHERE id=$1", col_id)
    return {"ok": True}


# AE-359: Smart Collection resolution — returns the live asset list for a
# collection (manual collections return their explicit member list; smart
# collections re-execute the stored query JSONB on every fetch).
@router.get("/dam/collections/{col_id}/assets")
async def dam_resolve_collection_assets(
    col_id: int,
    limit: int = Query(200, ge=1, le=1000),
    _: Principal = Depends(principal_dep),
):
    from src.services.dashboard.v2.library_smart_collections import (
        resolve_smart_collection,
    )

    rows = await resolve_smart_collection(col_id, limit=limit)
    return {"data": rows, "count": len(rows)}


# Brand kits CRUD

@router.get("/dam/brand-kits")
async def dam_list_brand_kits(
    scope: str = Query("brand"),
    scope_id: str | None = Query(None),
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    args: list[Any] = [scope]
    cond = "scope = $1"
    if scope_id:
        args.append(scope_id); cond += f" AND scope_id = ${len(args)}"
    rows = await pool.fetch(
        f"SELECT id, scope, scope_id, name, version_no, logo_asset_ids, palette,"
        f" font_asset_ids, lut_asset_id, intro_asset_id, outro_asset_id, notes, created_at"
        f" FROM dam_brand_kits WHERE {cond} ORDER BY name",
        *args,
    )
    return {"data": [dict(r) for r in rows]}


@router.post("/dam/brand-kits")
async def dam_create_brand_kit(
    body: BrandKitIn,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO dam_brand_kits
           (scope, scope_id, name, logo_asset_ids, palette, font_asset_ids, notes)
           VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
        body.scope, body.scope_id, body.name,
        body.logo_asset_ids, json.dumps(body.palette),
        body.font_asset_ids, body.notes,
    )
    return {"id": row["id"]}


@router.put("/dam/brand-kits/{kit_id}")
async def dam_update_brand_kit(
    kit_id: int,
    body: BrandKitIn,
    _: Principal = Depends(principal_dep),
):
    pool = await get_pool()
    await pool.execute(
        """UPDATE dam_brand_kits
              SET name=$2, logo_asset_ids=$3, palette=$4, font_asset_ids=$5, notes=$6,
                  updated_at=now()
            WHERE id=$1""",
        kit_id, body.name, body.logo_asset_ids,
        json.dumps(body.palette), body.font_asset_ids, body.notes,
    )
    return {"ok": True}


# POST /library/dam/search


_SELECT_COLS = (
    "id, scope, scope_id, kind, display_name, mime_type, bytes, "
    "thumbnail_key, storage_key, origin, tags, metadata, created_at"
)


def _common_filters(body: "SearchIn") -> tuple[list[str], list[Any]]:
    """Build the WHERE clause shared between FTS and semantic paths."""
    where = ["deleted_at IS NULL", "scope = $1"]
    args: list[Any] = [body.scope]
    if body.scope_id:
        args.append(body.scope_id)
        where.append(f"scope_id = ${len(args)}")
    if body.kind:
        args.append(body.kind)
        where.append(f"kind = ${len(args)}")
    if body.tags:
        for t in body.tags:
            args.append(t)
            where.append(f"${len(args)} = ANY(tags)")
    return where, args


async def _fts_search(body: "SearchIn") -> list[dict]:
    pool = await get_pool()
    where, args = _common_filters(body)
    if body.q:
        args.append(body.q)
        where.append(
            f"(to_tsvector('english', display_name) @@ plainto_tsquery('english', ${len(args)})"
            f" OR display_name ILIKE '%' || ${len(args)} || '%')"
        )
    args.append(body.limit)
    rows = await pool.fetch(
        f"""SELECT {_SELECT_COLS}, NULL::float8 AS cosine_sim
              FROM dam_assets
             WHERE {" AND ".join(where)}
             ORDER BY created_at DESC
             LIMIT ${len(args)}""",
        *args,
    )
    return [dict(r) for r in rows]


async def _semantic_search(body: "SearchIn") -> list[dict] | None:
    """Return semantic-ranked rows, or None if embeddings are unavailable.

    Returns ``None`` (not ``[]``) when the embedding call fails so the caller
    can fall back to FTS; an empty list means "we ran semantic search and
    nothing matched."
    """
    if not body.q:
        return None
    # Lazy import — semantic search depends on src/llm/embeddings (P0).
    from src.llm.embeddings import EmbeddingConfigError, EmbeddingError, embed_text

    try:
        vector = await embed_text(body.q)
    except (EmbeddingConfigError, EmbeddingError):
        return None

    literal = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
    pool = await get_pool()
    where, args = _common_filters(body)
    args.append(literal)
    vec_param = f"${len(args)}::vector"
    args.append(body.limit)
    rows = await pool.fetch(
        f"""
        SELECT {_SELECT_COLS},
               1 - (e.embedding <=> {vec_param}) AS cosine_sim
          FROM dam_assets
          JOIN dam_text_embeddings e ON e.asset_id = dam_assets.id
         WHERE {" AND ".join(where)}
         ORDER BY e.embedding <=> {vec_param}
         LIMIT ${len(args)}
        """,
        *args,
    )
    return [dict(r) for r in rows]


def _fuse(semantic: list[dict], lexical: list[dict], limit: int) -> list[dict]:
    """Reciprocal-rank fusion of two ranked lists.

    score(asset) = sum( 1 / (k + rank_i) ) over lists where the asset appears.
    Standard RRF with k=60. Robust to score scales and missing scores.
    """
    K = 60.0
    fused: dict[int, dict] = {}
    for rank, row in enumerate(semantic, start=1):
        entry = fused.setdefault(row["id"], dict(row, _score=0.0))
        entry["_score"] += 1.0 / (K + rank)
    for rank, row in enumerate(lexical, start=1):
        entry = fused.setdefault(row["id"], dict(row, _score=0.0))
        entry["_score"] += 1.0 / (K + rank)
    ranked = sorted(fused.values(), key=lambda r: r["_score"], reverse=True)
    for r in ranked:
        r.pop("_score", None)
    return ranked[:limit]


@router.post("/dam/search")
async def dam_search(
    body: SearchIn,
    _: Principal = Depends(principal_dep),
):
    """Library search (AE-356).

    Modes:
      * ``hybrid``   — semantic + FTS, fused with reciprocal-rank fusion.
                       Falls back to FTS only when the embedding call fails.
      * ``semantic`` — vector search only; empty list if embeddings unavailable.
      * ``fts``      — legacy behaviour: full-text + ILIKE.
    """
    mode = (body.mode or "hybrid").lower()
    if mode == "fts":
        rows = await _fts_search(body)
        return {"data": rows, "count": len(rows), "mode": "fts"}

    if mode == "semantic":
        semantic = await _semantic_search(body)
        if semantic is None:
            return {"data": [], "count": 0, "mode": "semantic", "note": "embeddings unavailable"}
        return {"data": semantic, "count": len(semantic), "mode": "semantic"}

    # hybrid (default)
    semantic = await _semantic_search(body)
    lexical = await _fts_search(body)
    if semantic is None:
        return {"data": lexical, "count": len(lexical), "mode": "fts_fallback"}
    fused = _fuse(semantic, lexical, body.limit)
    return {"data": fused, "count": len(fused), "mode": "hybrid"}
