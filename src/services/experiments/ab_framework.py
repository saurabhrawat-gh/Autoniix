"""A/B Testing Framework — Lightweight experiment system for intelligence layers.

Provides:
- Experiment definition (name, variants, traffic split)
- Deterministic variant assignment (hash-based, consistent per content_id)
- Outcome recording
- Statistical significance testing (chi-squared / t-test)
- Experiment lifecycle: draft → active → paused → completed

Usage:
    variant = await assign_variant("voice_local_vs_llm", content_id)
    # ... produce video using variant logic ...
    await record_outcome("voice_local_vs_llm", content_id, variant, {"retention": 0.45})
    results = await analyze_experiment("voice_local_vs_llm")
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

import numpy as np
import structlog

from src.db import get_pool

logger = structlog.get_logger()


# Variant Assignment

def _deterministic_variant(experiment_name: str, content_id: str, variants: list[str],
                           weights: list[float] | None = None) -> str:
    """Hash-based deterministic assignment — same content_id always gets same variant."""
    seed = hashlib.sha256(f"{experiment_name}:{content_id}".encode()).hexdigest()
    bucket = int(seed[:8], 16) % 10000  # 0-9999

    if not weights:
        weights = [1.0 / len(variants)] * len(variants)

    cumulative = 0.0
    for variant, weight in zip(variants, weights):
        cumulative += weight * 10000
        if bucket < cumulative:
            return variant
    return variants[-1]


# Experiment CRUD

async def create_experiment(name: str, description: str,
                            variants: list[dict],
                            traffic_pct: float = 100.0,
                            target_metric: str = "views") -> dict:
    """Create a new A/B experiment.
    
    variants: [{"name": "control", "weight": 0.5, "config": {...}},
               {"name": "treatment", "weight": 0.5, "config": {...}}]
    """
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO experiments (experiment_name, description, variants,
            traffic_pct, target_metric, status)
        VALUES ($1, $2, $3, $4, $5, 'draft')
        ON CONFLICT (experiment_name) DO UPDATE SET
            description = $2, variants = $3, traffic_pct = $4,
            target_metric = $5, updated_at = NOW()
    """, name, description, json.dumps(variants), traffic_pct, target_metric)

    logger.info("experiment.created", name=name, variants=len(variants))
    return {"name": name, "status": "draft", "variants": len(variants)}


async def activate_experiment(name: str) -> dict:
    pool = await get_pool()
    await pool.execute("""
        UPDATE experiments SET status = 'active', started_at = NOW(), updated_at = NOW()
        WHERE experiment_name = $1
    """, name)
    return {"name": name, "status": "active"}


async def pause_experiment(name: str) -> dict:
    pool = await get_pool()
    await pool.execute("""
        UPDATE experiments SET status = 'paused', updated_at = NOW()
        WHERE experiment_name = $1
    """, name)
    return {"name": name, "status": "paused"}


async def complete_experiment(name: str, winning_variant: str = "") -> dict:
    pool = await get_pool()
    await pool.execute("""
        UPDATE experiments SET status = 'completed', ended_at = NOW(),
            winning_variant = $2, updated_at = NOW()
        WHERE experiment_name = $1
    """, name, winning_variant)
    return {"name": name, "status": "completed", "winner": winning_variant}


async def list_experiments(status: str = "") -> list[dict]:
    pool = await get_pool()
    if status:
        rows = await pool.fetch(
            "SELECT * FROM experiments WHERE status = $1 ORDER BY created_at DESC", status)
    else:
        rows = await pool.fetch("SELECT * FROM experiments ORDER BY created_at DESC")
    return [dict(r) for r in rows]


# Assignment

async def assign_variant(experiment_name: str, content_id: str,
                          channel_id: str = "") -> dict:
    """Assign a variant for a content piece in an experiment.
    
    Returns: {"variant": "control", "config": {...}, "in_experiment": True}
    """
    pool = await get_pool()
    row = await pool.fetchrow("""
        SELECT experiment_name, variants, traffic_pct, status
        FROM experiments WHERE experiment_name = $1
    """, experiment_name)

    if not row or row["status"] != "active":
        return {"variant": "control", "config": {}, "in_experiment": False}

    variants_json = json.loads(row["variants"]) if isinstance(row["variants"], str) else row["variants"]
    traffic_pct = float(row["traffic_pct"])

    # Check if this content is in the experiment's traffic
    traffic_bucket = int(hashlib.sha256(content_id.encode()).hexdigest()[:4], 16) % 100
    if traffic_bucket >= traffic_pct:
        return {"variant": "control", "config": {}, "in_experiment": False}

    names = [v["name"] for v in variants_json]
    weights = [v.get("weight", 1.0 / len(variants_json)) for v in variants_json]

    variant_name = _deterministic_variant(experiment_name, content_id, names, weights)
    variant_config = next((v.get("config", {}) for v in variants_json if v["name"] == variant_name), {})

    # Record assignment
    await pool.execute("""
        INSERT INTO experiment_assignments (experiment_name, content_id, channel_id, variant_name)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (experiment_name, content_id) DO NOTHING
    """, experiment_name, content_id, channel_id, variant_name)

    return {"variant": variant_name, "config": variant_config, "in_experiment": True}


# Outcome Recording

async def record_outcome(experiment_name: str, content_id: str,
                          variant_name: str, metrics: dict) -> None:
    """Record outcome metrics for a variant assignment."""
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO experiment_outcomes (experiment_name, content_id, variant_name, metrics)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (experiment_name, content_id) DO UPDATE SET
            metrics = $4, recorded_at = NOW()
    """, experiment_name, content_id, variant_name, json.dumps(metrics))


# Statistical Analysis

async def analyze_experiment(experiment_name: str) -> dict:
    """Analyze experiment results with statistical significance testing."""
    pool = await get_pool()

    # Get experiment info
    exp = await pool.fetchrow(
        "SELECT * FROM experiments WHERE experiment_name = $1", experiment_name)
    if not exp:
        return {"error": "Experiment not found"}

    target_metric = exp["target_metric"]
    variants_json = json.loads(exp["variants"]) if isinstance(exp["variants"], str) else exp["variants"]

    # Get outcomes grouped by variant
    rows = await pool.fetch("""
        SELECT eo.variant_name, eo.metrics
        FROM experiment_outcomes eo
        WHERE eo.experiment_name = $1
        ORDER BY eo.variant_name
    """, experiment_name)

    if len(rows) < 10:
        return {
            "experiment": experiment_name,
            "status": "insufficient_data",
            "total_samples": len(rows),
            "min_required": 10,
        }

    # Group metrics by variant
    variant_data: dict[str, list[float]] = {}
    for row in rows:
        vn = row["variant_name"]
        metrics = json.loads(row["metrics"]) if isinstance(row["metrics"], str) else row["metrics"]
        value = float(metrics.get(target_metric, 0))
        if vn not in variant_data:
            variant_data[vn] = []
        variant_data[vn].append(value)

    # Compute stats per variant
    variant_stats = {}
    for vn, values in variant_data.items():
        arr = np.array(values)
        variant_stats[vn] = {
            "count": len(values),
            "mean": round(float(np.mean(arr)), 6),
            "std": round(float(np.std(arr)), 6),
            "median": round(float(np.median(arr)), 6),
            "min": round(float(np.min(arr)), 6),
            "max": round(float(np.max(arr)), 6),
        }

    # Significance test (two-sample t-test between first two variants)
    significance = {}
    variant_names = list(variant_data.keys())
    if len(variant_names) >= 2:
        a = np.array(variant_data[variant_names[0]])
        b = np.array(variant_data[variant_names[1]])

        if len(a) >= 5 and len(b) >= 5:
            # Welch's t-test
            n_a, n_b = len(a), len(b)
            mean_a, mean_b = np.mean(a), np.mean(b)
            var_a, var_b = np.var(a, ddof=1), np.var(b, ddof=1)

            se = np.sqrt(var_a / n_a + var_b / n_b)
            if se > 0:
                t_stat = (mean_a - mean_b) / se
                # Approximate degrees of freedom (Welch-Satterthwaite)
                df_num = (var_a / n_a + var_b / n_b) ** 2
                df_den = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
                df = df_num / df_den if df_den > 0 else 1

                # Rough p-value approximation (using normal for large df)
                from math import erfc, sqrt
                p_value = erfc(abs(t_stat) / sqrt(2))

                significance = {
                    "test": "welch_t_test",
                    "t_statistic": round(float(t_stat), 4),
                    "degrees_of_freedom": round(float(df), 1),
                    "p_value": round(float(p_value), 6),
                    "significant_at_005": p_value < 0.05,
                    "significant_at_001": p_value < 0.01,
                    "effect_size": round(float(mean_a - mean_b), 6),
                    "relative_improvement": round(
                        float((mean_b - mean_a) / mean_a * 100) if mean_a != 0 else 0, 2),
                }

    # Determine recommended winner
    winner = ""
    if variant_stats:
        winner = max(variant_stats, key=lambda v: variant_stats[v]["mean"])

    return {
        "experiment": experiment_name,
        "target_metric": target_metric,
        "total_samples": len(rows),
        "variant_stats": variant_stats,
        "significance": significance,
        "recommended_winner": winner,
        "status": exp["status"],
    }
