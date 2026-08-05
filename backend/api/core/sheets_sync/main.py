from __future__ import annotations

import json
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException

from core.config import settings
from core.db import close_pool, get_pool
from observability.metrics import instrument_app
from observability.sentry import init_sentry

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("sheets_sync.starting")
    yield
    await close_pool()
    logger.info("sheets_sync.stopped")


init_sentry("sheets_sync")

app = FastAPI(title="Google Sheets Sync Service", version="0.1.0", lifespan=lifespan)
instrument_app(app, service_name="sheets-sync")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sheets_sync"}


async def _get_sheets_client():
    """Initialize Google Sheets API client using service account credentials."""
    creds_json = settings.google_sheets_credentials_json
    if not creds_json:
        raise HTTPException(status_code=503, detail="No Google Sheets credentials configured")

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds_data = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_data,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return service.spreadsheets()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="google-api-python-client not installed. Run: pip install google-api-python-client google-auth",
        )


async def _sync_table_to_sheet(tab_name: str, query: str, columns: list[str]):
    """Generic: read from PostgreSQL and write to a Google Sheets tab."""
    pool = await get_pool()
    rows = await pool.fetch(query)

    if not rows:
        logger.info(f"sheets_sync.{tab_name}.no_data")
        return {"tab": tab_name, "rows_synced": 0}

    data = [columns]
    for row in rows:
        data.append([str(row.get(col, "") or "") for col in columns])

    sheets = await _get_sheets_client()
    sheet_id = settings.google_sheets_id

    range_name = f"{tab_name}!A1"
    sheets.values().clear(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A:ZZ",
    ).execute()

    sheets.values().update(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="RAW",
        body={"values": data},
    ).execute()

    logger.info(f"sheets_sync.{tab_name}.synced", rows=len(rows))
    return {"tab": tab_name, "rows_synced": len(rows)}


@app.post("/sync/system-config")
async def sync_system_config():
    return await _sync_table_to_sheet(
        "System_Config",
        "SELECT config_key, config_value, updated_at::text, updated_by FROM system_config ORDER BY config_key",
        ["config_key", "config_value", "updated_at", "updated_by"],
    )


@app.post("/sync/output-log")
async def sync_output_log():
    return await _sync_table_to_sheet(
        "Output_Log",
        """SELECT content_id, channel_id, status, content_mode, title, topic,
           research_depth_score::text, fact_confidence_score::text, idea_score::text,
           script_structure_score::text, hook_retention_score::text,
           voice_quality_score::text, voice_duration_s::text,
           thumbnail_score::text, direction_score::text, production_score::text,
           final_composite_score::text, youtube_video_id, total_cost::text,
           checkpoint, error_message, created_at::text, updated_at::text
           FROM videos ORDER BY created_at DESC LIMIT 500""",
        [
            "content_id",
            "channel_id",
            "status",
            "content_mode",
            "title",
            "topic",
            "research_depth_score",
            "fact_confidence_score",
            "idea_score",
            "script_structure_score",
            "hook_retention_score",
            "voice_quality_score",
            "voice_duration_s",
            "thumbnail_score",
            "direction_score",
            "production_score",
            "final_composite_score",
            "youtube_video_id",
            "total_cost",
            "checkpoint",
            "error_message",
            "created_at",
            "updated_at",
        ],
    )


@app.post("/sync/api-usage")
async def sync_api_usage():
    return await _sync_table_to_sheet(
        "API_Usage_Tracker",
        """SELECT date::text, openai_tokens_in::text, openai_tokens_out::text, openai_cost::text,
           claude_tokens_in::text, claude_tokens_out::text, claude_cost::text,
           gemini_tokens::text, gemini_cost::text, elevenlabs_chars::text,
           dalle_calls::text, youtube_api_units::text, pixabay_calls::text,
           pexels_calls::text, serpapi_calls::text, remotion_renders::text,
           total_cost::text, channel_id, content_id
           FROM api_usage ORDER BY created_at DESC LIMIT 1000""",
        [
            "date",
            "openai_tokens_in",
            "openai_tokens_out",
            "openai_cost",
            "claude_tokens_in",
            "claude_tokens_out",
            "claude_cost",
            "gemini_tokens",
            "gemini_cost",
            "elevenlabs_chars",
            "dalle_calls",
            "youtube_api_units",
            "pixabay_calls",
            "pexels_calls",
            "serpapi_calls",
            "remotion_renders",
            "total_cost",
            "channel_id",
            "content_id",
        ],
    )


@app.post("/sync/feedback-loop")
async def sync_feedback_loop():
    return await _sync_table_to_sheet(
        "Feedback_Loop",
        """SELECT video_id, channel_id, title, idea_score::text, script_score::text,
           thumbnail_score::text, hook_retention_score::text, final_score::text,
           content_mode, status, yt_video_id, yt_views::text, yt_likes::text,
           yt_comments::text, yt_ctr::text, yt_avg_view_duration::text,
           engagement_rate::text, performance_tier, analytics_status,
           created_at::text, updated_at::text
           FROM feedback_loop ORDER BY created_at DESC LIMIT 500""",
        [
            "video_id",
            "channel_id",
            "title",
            "idea_score",
            "script_score",
            "thumbnail_score",
            "hook_retention_score",
            "final_score",
            "content_mode",
            "status",
            "yt_video_id",
            "yt_views",
            "yt_likes",
            "yt_comments",
            "yt_ctr",
            "yt_avg_view_duration",
            "engagement_rate",
            "performance_tier",
            "analytics_status",
            "created_at",
            "updated_at",
        ],
    )


@app.post("/sync/trend-intelligence")
async def sync_trend_intelligence():
    return await _sync_table_to_sheet(
        "Trend_Intelligence",
        """SELECT trend_id, channel_id, niche, trend_type, trend_title, trend_description,
           source, source_url, detected_at::text, relevance_score::text,
           virality_potential::text, competition_level, freshness, status,
           used_in_video_id, expires_at::text
           FROM trend_intelligence WHERE status = 'active' ORDER BY detected_at DESC LIMIT 500""",
        [
            "trend_id",
            "channel_id",
            "niche",
            "trend_type",
            "trend_title",
            "trend_description",
            "source",
            "source_url",
            "detected_at",
            "relevance_score",
            "virality_potential",
            "competition_level",
            "freshness",
            "status",
            "used_in_video_id",
            "expires_at",
        ],
    )


@app.post("/sync/all")
async def sync_all():
    """Sync all tables to Google Sheets."""
    results = []
    for sync_fn in [sync_system_config, sync_output_log, sync_api_usage, sync_feedback_loop, sync_trend_intelligence]:
        try:
            result = await sync_fn()
            results.append(result)
        except Exception as exc:
            results.append({"tab": sync_fn.__name__, "error": str(exc)})
    return {"status": "completed", "results": results}


if __name__ == "__main__":
    uvicorn.run("services_api.sheets_sync.main:app", host="0.0.0.0", port=8011, log_level="info")
