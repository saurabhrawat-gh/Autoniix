"""Import locally-downloaded paid-subscription assets (Motion Array, Envato
Elements, etc.) into the Autoniix local asset library.

After importing, every render automatically picks up these assets via the
``_local_library`` provider in the asset chain — zero marginal cost per video.

Supported asset types (auto-detected from file extension unless --asset-type
is supplied):

  stock_video  — .mp4  .mov  .avi  .webm
  bg_music     — .mp3  .wav  .aiff .flac .ogg
  sfx          — same extensions; pass ``--asset-type sfx`` to distinguish
  font         — .ttf  .otf  .woff .woff2
  lut          — .cube .3dl  .lut
  image        — .png  .jpg  .jpeg .webp  .tiff

Usage::

    # Dry-run first — see what would be imported
    python scripts/import_local_assets.py --dir ~/Downloads/MotionArray/music \\
        --niche tech --tags "cinematic,background music" --dry-run

    # Import bg music
    python scripts/import_local_assets.py --dir ~/Downloads/MotionArray/music \\
        --niche tech --tags "cinematic,background music"

    # Import stock footage
    python scripts/import_local_assets.py --dir ~/Downloads/MotionArray/footage \\
        --asset-type stock_video --niche tech --quality 9.0

    # Import LUTs
    python scripts/import_local_assets.py --dir ~/Downloads/MotionArray/luts \\
        --asset-type lut --niche all --tags "color grading,cinematic"

    # Import fonts
    python scripts/import_local_assets.py --dir ~/Downloads/MotionArray/fonts \\
        --asset-type font --niche all --tags "modern,sans-serif,display"

    # Import everything from a root folder (auto-detects asset type per file)
    python scripts/import_local_assets.py --dir ~/Downloads/MotionArray \\
        --niche tech --provider motionarray

Idempotent: existing ``(provider, minio_key)`` rows are skipped silently.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import structlog

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logger = structlog.get_logger()

# ── Extension → asset_type map ───────────────────────────────────────

_EXT_MAP: dict[str, str] = {
    ".mp4": "stock_video",
    ".mov": "stock_video",
    ".avi": "stock_video",
    ".webm": "stock_video",
    ".mp3": "bg_music",
    ".wav": "bg_music",
    ".aiff": "bg_music",
    ".aif": "bg_music",
    ".flac": "bg_music",
    ".ogg": "bg_music",
    ".ttf": "font",
    ".otf": "font",
    ".woff": "font",
    ".woff2": "font",
    ".cube": "lut",
    ".3dl": "lut",
    ".lut": "lut",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tiff": "image",
    ".tif": "image",
}

_CONTENT_TYPE_MAP: dict[str, str] = {
    "stock_video": "video/mp4",
    "bg_music": "audio/mpeg",
    "sfx": "audio/mpeg",
    "font": "font/ttf",
    "lut": "application/octet-stream",
    "image": "image/png",
}

_EXT_CONTENT_TYPE: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".aiff": "audio/aiff",
    ".aif": "audio/aiff",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".cube": "application/octet-stream",
    ".3dl": "application/octet-stream",
    ".lut": "application/octet-stream",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


# ── Metadata extraction ──────────────────────────────────────────────

def _slug_to_words(filename: str) -> str:
    """'epic-cinematic-bgm_v2' → 'epic cinematic bgm v2'"""
    stem = Path(filename).stem
    return re.sub(r"[-_]+", " ", stem).strip().lower()


def _ffprobe_metadata(path: Path) -> dict:
    """Extract duration, width, height via ffprobe. Returns {} on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0) or 0)
        width = height = 0
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0) or 0)
                height = int(stream.get("height", 0) or 0)
                break
        return {"duration": duration, "width": width, "height": height}
    except Exception:
        return {}


def _image_metadata(path: Path) -> dict:
    """Extract width/height from image via Pillow."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            w, h = img.size
        return {"width": w, "height": h, "duration": 0.0}
    except Exception:
        return {}


def get_metadata(path: Path, asset_type: str) -> dict:
    """Return {duration, width, height} for a given path + asset_type."""
    if asset_type in ("stock_video", "bg_music", "sfx"):
        meta = _ffprobe_metadata(path)
        return {
            "duration": meta.get("duration", 0.0),
            "width": meta.get("width", 0),
            "height": meta.get("height", 0),
        }
    if asset_type == "image":
        return _image_metadata(path)
    # fonts and LUTs have no meaningful media metadata
    return {"duration": 0.0, "width": 0, "height": 0}


# ── Query generation ─────────────────────────────────────────────────

def generate_queries(
    path: Path,
    asset_type: str,
    niche: str,
    extra_tags: list[str],
) -> list[str]:
    """Generate 2-4 meaningful query strings for semantic indexing."""
    name_words = _slug_to_words(path.name)
    all_tags = [t.strip() for t in extra_tags if t.strip()]

    queries: list[str] = []

    # Primary: filename words + niche
    primary = name_words
    if niche and niche != "all":
        primary = f"{niche} {name_words}"
    queries.append(primary)

    # Secondary: asset_type + tags
    if all_tags:
        tag_str = " ".join(all_tags[:4])
        queries.append(f"{asset_type.replace('_', ' ')} {tag_str}")

    # Tertiary: niche + asset_type (generic fallback that always matches)
    if niche and niche != "all":
        queries.append(f"{niche} {asset_type.replace('_', ' ')}")
    else:
        queries.append(asset_type.replace("_", " "))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            unique.append(q)
    return unique


# ── SBERT embedding ──────────────────────────────────────────────────

def _try_embed(query: str) -> Optional[list[float]]:
    try:
        from src.services.assets import semantic_ranker
        import numpy as np
        model = semantic_ranker._get_model()
        if model is None:
            return None
        vec = model.encode([query], normalize_embeddings=True)[0]
        return [float(x) for x in np.asarray(vec).tolist()]
    except Exception:
        return None


# ── File discovery ───────────────────────────────────────────────────

def discover_files(directory: Path, asset_type_override: Optional[str]) -> list[tuple[Path, str]]:
    """Walk directory recursively; return [(path, asset_type)] for known extensions."""
    results: list[tuple[Path, str]] = []
    for p in sorted(directory.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if asset_type_override:
            # Still only process known media extensions
            if ext not in _EXT_MAP:
                continue
            results.append((p, asset_type_override))
        else:
            atype = _EXT_MAP.get(ext)
            if atype:
                results.append((p, atype))
    return results


# ── Core import logic ────────────────────────────────────────────────

async def import_asset(
    path: Path,
    asset_type: str,
    provider: str,
    niche: str,
    extra_tags: list[str],
    quality: float,
    dry_run: bool,
    storage,
    pool,
) -> bool:
    """Import a single file. Returns True if inserted/would insert."""
    ext = path.suffix.lower()
    content_type = _EXT_CONTENT_TYPE.get(ext, "application/octet-stream")
    safe_name = re.sub(r"[^\w.\-]", "_", path.name)
    minio_key = f"library/{provider}/{asset_type}/{niche}/{safe_name}"

    queries = generate_queries(path, asset_type, niche, extra_tags)
    meta = get_metadata(path, asset_type)
    tags_str = ", ".join(extra_tags) if extra_tags else _slug_to_words(path.name)

    if dry_run:
        logger.info(
            "dry_run.would_import",
            file=str(path),
            asset_type=asset_type,
            minio_key=minio_key,
            queries=queries,
            duration=meta["duration"],
            resolution=f"{meta['width']}x{meta['height']}",
        )
        return True

    # Idempotency check
    existing = await pool.fetchval(
        "SELECT id FROM asset_library WHERE minio_key = $1 LIMIT 1",
        minio_key,
    )
    if existing:
        logger.debug("import.skip_existing", minio_key=minio_key)
        return False

    # Upload to MinIO
    try:
        data = path.read_bytes()
        from src.providers.storage.base import StorageUpload
        up = await storage.upload(StorageUpload(
            key=minio_key,
            data=data,
            content_type=content_type,
            metadata={
                "provider": provider,
                "asset_type": asset_type,
                "niche": niche,
                "original_filename": path.name,
            },
        ))
        logger.info("import.uploaded", key=up.key, size=up.size_bytes)
    except Exception as exc:
        logger.error("import.upload_failed", file=str(path), error=str(exc))
        return False

    # Insert one row per query (enables semantic cache hits)
    inserted_count = 0
    for query in queries:
        qhash = hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]
        embedding = _try_embed(query)
        asset_url = f"{provider}://{minio_key}"

        try:
            await pool.execute(
                """
                INSERT INTO asset_library (
                    query_hash, query_text, provider, asset_url, minio_key,
                    asset_type, resolution_width, resolution_height,
                    duration_s, dominant_colors, quality_score, relevance_score,
                    use_count, query_embedding, license_type, tags
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,0,$13,$14,$15)
                ON CONFLICT DO NOTHING
                """,
                qhash, query, provider, asset_url, minio_key,
                asset_type, meta["width"], meta["height"], meta["duration"],
                json.dumps([]),
                quality, quality,
                embedding,
                f"{provider}_subscription",
                tags_str[:500],
            )
            inserted_count += 1
        except Exception as exc:
            logger.warning("import.insert_failed", query=query, error=str(exc))

    if inserted_count > 0:
        logger.info(
            "import.done",
            file=path.name,
            asset_type=asset_type,
            queries=inserted_count,
            minio_key=minio_key,
        )
    return inserted_count > 0


async def run_import(
    directory: Path,
    asset_type_override: Optional[str],
    provider: str,
    niche: str,
    extra_tags: list[str],
    quality: float,
    dry_run: bool,
) -> tuple[int, int]:
    """Import all assets in directory. Returns (total_files, imported_count)."""
    files = discover_files(directory, asset_type_override)
    if not files:
        logger.warning("import.no_files_found", directory=str(directory))
        return 0, 0

    logger.info(
        "import.start",
        files=len(files),
        directory=str(directory),
        dry_run=dry_run,
    )

    if dry_run:
        for path, atype in files:
            await import_asset(
                path=path, asset_type=atype, provider=provider,
                niche=niche, extra_tags=extra_tags, quality=quality,
                dry_run=True, storage=None, pool=None,
            )
        return len(files), len(files)

    from src.db import get_pool, close_pool
    from src.providers.boot import boot_providers
    from src.providers.registry import ProviderRegistry

    boot_providers()
    storage = ProviderRegistry.get("storage")
    pool = await get_pool()

    imported = 0
    for path, atype in files:
        ok = await import_asset(
            path=path, asset_type=atype, provider=provider,
            niche=niche, extra_tags=extra_tags, quality=quality,
            dry_run=False, storage=storage, pool=pool,
        )
        if ok:
            imported += 1

    await close_pool()
    return len(files), imported


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Import local paid-subscription assets into the Autoniix asset library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--dir", required=True,
                    help="Directory containing downloaded assets (walked recursively)")
    ap.add_argument("--asset-type", dest="asset_type",
                    choices=["stock_video", "bg_music", "sfx", "font", "lut", "image"],
                    help="Override auto-detection. If omitted, inferred from file extension")
    ap.add_argument("--provider", default="motionarray",
                    help="Provider label stored in DB (default: motionarray)")
    ap.add_argument("--niche", default="all",
                    help="Niche this asset set belongs to (tech/health/finance/all/etc.)")
    ap.add_argument("--tags", default="",
                    help="Comma-separated tags added to every asset (e.g. 'cinematic,epic')")
    ap.add_argument("--quality", type=float, default=9.0,
                    help="Quality score 0-10 for all imported assets (default: 9.0)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be imported without writing to DB or MinIO")
    args = ap.parse_args()

    source_dir = Path(args.dir).expanduser().resolve()
    if not source_dir.exists():
        ap.error(f"--dir does not exist: {source_dir}")
    if not source_dir.is_dir():
        ap.error(f"--dir is not a directory: {source_dir}")

    extra_tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    total, imported = asyncio.run(run_import(
        directory=source_dir,
        asset_type_override=args.asset_type,
        provider=args.provider,
        niche=args.niche,
        extra_tags=extra_tags,
        quality=args.quality,
        dry_run=args.dry_run,
    ))

    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{mode}import_local_assets: {imported}/{total} files imported")
    if args.dry_run:
        print("  Run without --dry-run to write to MinIO + DB.")


if __name__ == "__main__":
    main()
