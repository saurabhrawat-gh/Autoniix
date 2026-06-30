from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.db import close_pool, get_pool
from src.schemas.common import HealthResponse, ServiceResponse

from src.services.experiments.ab_framework import (
    create_experiment,
    activate_experiment,
    pause_experiment,
    complete_experiment,
    list_experiments,
    analyze_experiment,
)
from src.services.experiments.observability import (
    get_decision_summary,
    get_cost_savings,
    get_model_health_summary,
)
from src.observability.metrics import instrument_app

logger = structlog.get_logger()


class ChannelCreate(BaseModel):
    channel_id: str
    channel_name: str
    niche: str
    content_mode: str = "long_form"
    voice_id: str = ""
    brand_config: dict = Field(default_factory=dict)


class ChannelUpdate(BaseModel):
    channel_name: str | None = None
    niche: str | None = None
    content_mode: str | None = None
    voice_id: str | None = None
    brand_config: dict | None = None
    status: str | None = None


class ConfigUpdate(BaseModel):
    config_value: str
    description: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("admin.starting")
    yield
    await close_pool()
    logger.info("admin.stopped")


from src.observability.sentry import init_sentry
init_sentry("admin")

app = FastAPI(title="Admin Service", version="0.1.0", lifespan=lifespan)


instrument_app(app, service_name="admin")
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(service="admin")



@app.get("/dashboard", response_model=ServiceResponse)
async def dashboard():
    pool = await get_pool()

    channels = await pool.fetchval("SELECT COUNT(*) FROM channels WHERE status = 'active'")
    total_videos = await pool.fetchval("SELECT COUNT(*) FROM videos")
    delivered = await pool.fetchval("SELECT COUNT(*) FROM videos WHERE status = 'delivered'")
    failed = await pool.fetchval("SELECT COUNT(*) FROM videos WHERE status = 'failed'")
    today_cost = await pool.fetchval(
        "SELECT COALESCE(SUM(total_cost), 0) FROM videos WHERE created_at::date = $1",
        date.today(),
    )
    total_cost = await pool.fetchval("SELECT COALESCE(SUM(cost_usd), 0) FROM api_usage")

    config_rows = await pool.fetch("SELECT config_key, config_value FROM system_config")
    config = {r["config_key"]: r["config_value"] for r in config_rows}

    return ServiceResponse(
        status="success",
        data={
            "active_channels": channels,
            "total_videos": total_videos,
            "delivered_videos": delivered,
            "failed_videos": failed,
            "today_cost_usd": float(today_cost),
            "total_cost_usd": float(total_cost),
            "system_config": config,
        },
    )



@app.get("/channels", response_model=ServiceResponse)
async def list_channels():
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT channel_id, channel_name, niche, content_mode, voice_id, status, "
        "brand_config, created_at FROM channels ORDER BY channel_id"
    )
    channels = [
        {
            "channel_id": r["channel_id"],
            "channel_name": r["channel_name"],
            "niche": r["niche"],
            "content_mode": r["content_mode"],
            "voice_id": r["voice_id"],
            "status": r["status"],
            "brand_config": json.loads(r["brand_config"]) if r["brand_config"] else {},
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
    return ServiceResponse(status="success", data={"channels": channels, "count": len(channels)})


@app.post("/channels", response_model=ServiceResponse)
async def create_channel(req: ChannelCreate):
    pool = await get_pool()
    try:
        await pool.execute(
            "INSERT INTO channels (channel_id, channel_name, niche, content_mode, voice_id, brand_config) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            req.channel_id, req.channel_name, req.niche, req.content_mode,
            req.voice_id, json.dumps(req.brand_config),
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail=f"Channel {req.channel_id} already exists")
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info("admin.channel_created", channel_id=req.channel_id)
    return ServiceResponse(status="success", data={"channel_id": req.channel_id})


@app.put("/channels/{channel_id}", response_model=ServiceResponse)
async def update_channel(channel_id: str, req: ChannelUpdate):
    pool = await get_pool()
    sets, vals, idx = [], [], 1

    for field, col in [
        ("channel_name", "channel_name"), ("niche", "niche"),
        ("content_mode", "content_mode"), ("voice_id", "voice_id"),
        ("status", "status"),
    ]:
        val = getattr(req, field, None)
        if val is not None:
            sets.append(f"{col} = ${idx}")
            vals.append(val)
            idx += 1

    if req.brand_config is not None:
        sets.append(f"brand_config = ${idx}")
        vals.append(json.dumps(req.brand_config))
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets.append(f"updated_at = NOW()")
    vals.append(channel_id)
    query = f"UPDATE channels SET {', '.join(sets)} WHERE channel_id = ${idx}"
    await pool.execute(query, *vals)

    logger.info("admin.channel_updated", channel_id=channel_id)
    return ServiceResponse(status="success", data={"channel_id": channel_id})



@app.get("/config", response_model=ServiceResponse)
async def get_config():
    pool = await get_pool()
    rows = await pool.fetch("SELECT config_key, config_value, description, updated_at FROM system_config")
    config = [
        {"key": r["config_key"], "value": r["config_value"],
         "description": r["description"], "updated_at": r["updated_at"].isoformat()}
        for r in rows
    ]
    return ServiceResponse(status="success", data={"config": config})


@app.put("/config/{key}", response_model=ServiceResponse)
async def update_config(key: str, req: ConfigUpdate):
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE system_config SET config_value = $1, description = COALESCE($2, description), "
        "updated_at = NOW() WHERE config_key = $3",
        req.config_value, req.description, key,
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")

    logger.info("admin.config_updated", key=key, value=req.config_value)
    return ServiceResponse(status="success", data={"key": key, "value": req.config_value})



@app.post("/emergency-stop", response_model=ServiceResponse)
async def emergency_stop():
    pool = await get_pool()
    await pool.execute(
        "UPDATE system_config SET config_value = 'true', updated_at = NOW() WHERE config_key = 'emergency_stop'"
    )
    logger.warning("admin.emergency_stop_activated")
    return ServiceResponse(status="success", data={"emergency_stop": True})


@app.post("/emergency-resume", response_model=ServiceResponse)
async def emergency_resume():
    pool = await get_pool()
    await pool.execute(
        "UPDATE system_config SET config_value = 'false', updated_at = NOW() WHERE config_key = 'emergency_stop'"
    )
    logger.info("admin.emergency_stop_cleared")
    return ServiceResponse(status="success", data={"emergency_stop": False})



@app.get("/videos", response_model=ServiceResponse)
async def list_videos(channel_id: str | None = None, status: str | None = None, limit: int = 50):
    pool = await get_pool()
    query = "SELECT content_id, channel_id, status, title, content_mode, total_cost, youtube_video_id, created_at FROM videos"
    conditions, params, idx = [], [], 1

    if channel_id:
        conditions.append(f"channel_id = ${idx}")
        params.append(channel_id)
        idx += 1
    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" ORDER BY created_at DESC LIMIT ${idx}"
    params.append(limit)

    rows = await pool.fetch(query, *params)
    videos = [
        {
            "content_id": r["content_id"],
            "channel_id": r["channel_id"],
            "status": r["status"],
            "title": r["title"],
            "content_mode": r["content_mode"],
            "total_cost": float(r["total_cost"]) if r["total_cost"] else 0,
            "youtube_video_id": r["youtube_video_id"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
    return ServiceResponse(status="success", data={"videos": videos, "count": len(videos)})



class ExperimentCreate(BaseModel):
    name: str
    description: str = ""
    variants: list[dict] = Field(default_factory=list)
    traffic_pct: float = 100.0
    target_metric: str = "views"


@app.post("/experiments", response_model=ServiceResponse)
async def create_exp(req: ExperimentCreate):
    result = await create_experiment(req.name, req.description, req.variants,
                                     req.traffic_pct, req.target_metric)
    return ServiceResponse(status="success", data=result)


@app.post("/experiments/{name}/activate", response_model=ServiceResponse)
async def activate_exp(name: str):
    result = await activate_experiment(name)
    return ServiceResponse(status="success", data=result)


@app.post("/experiments/{name}/pause", response_model=ServiceResponse)
async def pause_exp(name: str):
    result = await pause_experiment(name)
    return ServiceResponse(status="success", data=result)


@app.post("/experiments/{name}/complete", response_model=ServiceResponse)
async def complete_exp(name: str, winner: str = ""):
    result = await complete_experiment(name, winner)
    return ServiceResponse(status="success", data=result)


@app.get("/experiments", response_model=ServiceResponse)
async def list_exps(status: str = ""):
    result = await list_experiments(status)
    return ServiceResponse(status="success", data={"experiments": result})


@app.get("/experiments/{name}/results", response_model=ServiceResponse)
async def experiment_results(name: str):
    result = await analyze_experiment(name)
    return ServiceResponse(status="success", data=result)



@app.get("/intelligence/decisions", response_model=ServiceResponse)
async def intelligence_decisions(days: int = 30, service: str = ""):
    """Decision path breakdown across all services."""
    result = await get_decision_summary(days, service)
    return ServiceResponse(status="success", data=result)


@app.get("/intelligence/savings", response_model=ServiceResponse)
async def intelligence_savings(days: int = 30):
    """Cost savings from local intelligence vs LLM fallback."""
    result = await get_cost_savings(days)
    return ServiceResponse(status="success", data=result)


@app.get("/intelligence/models", response_model=ServiceResponse)
async def intelligence_models():
    """Health status of all ML models."""
    result = await get_model_health_summary()
    return ServiceResponse(status="success", data={"models": result})


if __name__ == "__main__":
    uvicorn.run("src.services.admin.main:app", host="0.0.0.0", port=8009, log_level="info")
