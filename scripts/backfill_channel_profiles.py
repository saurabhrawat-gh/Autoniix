"""Backfill channel_profiles + channel_pillars for pre-existing channels.

Idempotent: only writes when no profile row exists for a channel.

Usage:
    python -m scripts.backfill_channel_profiles
"""

from __future__ import annotations

import asyncio
import json

import asyncpg
import structlog

from core.config import settings

logger = structlog.get_logger()


async def main() -> None:
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )
    try:
        channels = await conn.fetch(
            "SELECT channel_id, channel_name, niche, sub_niche, content_mode, "
            "       brand_voice, narrative_rhythm, emotional_contract, "
            "       intellectual_lens, target_audience, primary_format_long, "
            "       primary_format_short, thumbnail_style "
            "  FROM channels"
        )
        logger.info("backfill.start", channels=len(channels))
        created_profiles = 0
        created_pillars = 0
        for c in channels:
            existing = await conn.fetchval("SELECT 1 FROM channel_profiles WHERE channel_id=$1", c["channel_id"])
            if existing:
                continue
            payload = {
                "tone": c["brand_voice"],
                "narration_style": c["narrative_rhythm"],
                "brand_personality": c["emotional_contract"],
                "intellectual_lens": c["intellectual_lens"],
                "target_audience": c["target_audience"],
            }
            payload = {k: v for k, v in payload.items() if v}
            score = int(round((len(payload) / 5) * 100))
            await conn.execute(
                """INSERT INTO channel_profiles
                    (channel_id, payload, brand_personality, tone, completeness_score)
                   VALUES ($1, $2::jsonb, $3, $4, $5)""",
                c["channel_id"],
                json.dumps(payload),
                c["emotional_contract"],
                c["brand_voice"],
                score,
            )
            created_profiles += 1
            # Seed a single core pillar from niche.
            if c["niche"]:
                already = await conn.fetchval(
                    "SELECT COUNT(*) FROM channel_pillars WHERE channel_id=$1",
                    c["channel_id"],
                )
                if not already:
                    await conn.execute(
                        """INSERT INTO channel_pillars (channel_id, name, description, position)
                           VALUES ($1, $2, $3, 0)""",
                        c["channel_id"],
                        c["niche"],
                        f"Core pillar derived from niche {c['niche']!r} during backfill",
                    )
                    created_pillars += 1
        logger.info("backfill.done", profiles=created_profiles, pillars=created_pillars)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
