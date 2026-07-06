"""Thumbnail CTR Predictor — ML model to predict click-through rate.

Uses historical thumbnail features + actual CTR data to train a predictor.
Follows same GBM + self-learning pattern as research/script services.

Intelligence cost: $0.00 — sklearn + numpy, all local.
"""
from __future__ import annotations

import asyncio
import json
import pickle
from typing import Any

import numpy as np
import structlog

from core.db import get_pool

logger = structlog.get_logger()

FEATURE_NAMES = [
    "has_face", "face_area_ratio", "text_area_ratio",
    "color_contrast_score", "brightness_score", "saturation_score",
    "rule_of_thirds_score", "text_word_count",
    "local_composition_score",
]


async def extract_thumbnail_features(content_id: str, channel_id: str,
                                      composition: dict, variant_id: int = 0,
                                      text_overlay: str = "") -> dict:
    """Extract and store thumbnail features for ML pipeline."""
    features_data = composition.get("features", {})

    features = {
        "has_face": features_data.get("has_face", False),
        "face_area_ratio": features_data.get("face_area_ratio", 0),
        "text_area_ratio": 0.0,
        "color_contrast_score": features_data.get("contrast", 3.0),
        "brightness_score": features_data.get("brightness", 0.5),
        "saturation_score": features_data.get("saturation", 0.3),
        "rule_of_thirds_score": features_data.get("rule_of_thirds_score", 5.0),
        "text_word_count": len(text_overlay.split()) if text_overlay else 0,
        "local_composition_score": composition.get("composition_score", 5.0),
    }

    if features["text_word_count"] > 0:
        features["text_area_ratio"] = min(0.4, features["text_word_count"] * 0.06)

    dominant_colors = features_data.get("dominant_colors", [])
    dominant_rgb = str(dominant_colors[0]["rgb"]) if dominant_colors else ""

    try:
        pool = await get_pool()
        await pool.execute("""
            INSERT INTO thumbnail_features (content_id, channel_id, variant_id,
                has_face, face_area_ratio, text_area_ratio, dominant_color_rgb,
                color_contrast_score, brightness_score, saturation_score,
                rule_of_thirds_score, text_word_count,
                local_composition_score, predicted_ctr)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
            content_id, channel_id, variant_id,
            features["has_face"], features["face_area_ratio"],
            features["text_area_ratio"], dominant_rgb,
            features["color_contrast_score"], features["brightness_score"],
            features["saturation_score"], features["rule_of_thirds_score"],
            features["text_word_count"], features["local_composition_score"],
            0.0)
    except Exception as e:
        logger.warning("ctr_predictor.store_failed", error=str(e))

    return features


async def predict_ctr(features: dict, niche: str) -> float | None:
    """Predict CTR using trained ML model. Returns None if no model."""
    try:
        pool = await get_pool()
        row = await pool.fetchrow("""
            SELECT model_blob, feature_names, metrics FROM script_models
            WHERE model_name = 'thumbnail_ctr_predictor' AND niche = $1 AND is_active = TRUE
            ORDER BY created_at DESC LIMIT 1
        """, niche)

        if not row or not row["model_blob"]:
            return None

        model = pickle.loads(row["model_blob"])
        stored_features = json.loads(row["feature_names"]) if row["feature_names"] else FEATURE_NAMES

        X = np.array([[float(features.get(f, 0)) for f in stored_features]])
        prediction = float(model.predict(X)[0])
        return round(max(0, min(0.30, prediction)), 4)

    except Exception as e:
        logger.warning("ctr_predictor.predict_failed", error=str(e))
        return None


async def ingest_ctr_outcome(content_id: str, channel_id: str,
                              actual_ctr: float, impressions: int) -> bool:
    """Ingest actual CTR data for ML training."""
    try:
        pool = await get_pool()

        avg_row = await pool.fetchrow("""
            SELECT AVG(actual_ctr) as avg_ctr FROM thumbnail_outcomes
            WHERE channel_id = $1 AND actual_ctr IS NOT NULL
        """, channel_id)
        avg_ctr = float(avg_row["avg_ctr"]) if avg_row and avg_row["avg_ctr"] else 0.05
        is_above_avg = actual_ctr > avg_ctr

        await pool.execute("""
            INSERT INTO thumbnail_outcomes (content_id, channel_id,
                actual_ctr, impressions, clicks, is_above_avg_ctr)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (content_id) DO UPDATE SET
                actual_ctr = EXCLUDED.actual_ctr,
                impressions = EXCLUDED.impressions,
                is_above_avg_ctr = EXCLUDED.is_above_avg_ctr,
                updated_at = NOW()
        """, content_id, channel_id, actual_ctr, impressions,
            int(actual_ctr * impressions), is_above_avg)
        return True
    except Exception as e:
        logger.warning("ctr_predictor.ingest_failed", error=str(e))
        return False


async def train_ctr_model(niche: str) -> dict:
    """Train CTR prediction model from historical data."""
    try:
        pool = await get_pool()
        rows = await pool.fetch("""
            SELECT tf.has_face, tf.face_area_ratio, tf.text_area_ratio,
                   tf.color_contrast_score, tf.brightness_score, tf.saturation_score,
                   tf.rule_of_thirds_score, tf.text_word_count, tf.local_composition_score,
                   to2.actual_ctr
            FROM thumbnail_features tf
            JOIN thumbnail_outcomes to2 ON tf.content_id = to2.content_id
            JOIN channels c ON tf.channel_id = c.channel_id
            WHERE c.niche = $1 AND to2.actual_ctr IS NOT NULL
        """, niche)

        if len(rows) < 20:
            return {"status": "insufficient_data", "samples": len(rows)}

        X = np.array([[
            1.0 if r["has_face"] else 0.0,
            float(r["face_area_ratio"] or 0),
            float(r["text_area_ratio"] or 0),
            float(r["color_contrast_score"] or 0),
            float(r["brightness_score"] or 0),
            float(r["saturation_score"] or 0),
            float(r["rule_of_thirds_score"] or 0),
            float(r["text_word_count"] or 0),
            float(r["local_composition_score"] or 0),
        ] for r in rows])
        y = np.array([float(r["actual_ctr"]) for r in rows])

        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score

        model = GradientBoostingRegressor(
            n_estimators=50, max_depth=3, learning_rate=0.1, random_state=42)
        scores = cross_val_score(model, X, y, cv=min(5, len(y) // 3), scoring="r2")
        mean_r2 = float(np.mean(scores))

        model.fit(X, y)
        model_blob = pickle.dumps(model)

        metrics = {
            "r2": round(mean_r2, 4),
            "samples": len(rows),
            "mean_ctr": round(float(np.mean(y)), 4),
        }

        await pool.execute("""
            UPDATE script_models SET is_active = FALSE
            WHERE model_name = 'thumbnail_ctr_predictor' AND niche = $1
        """, niche)

        await pool.execute("""
            INSERT INTO script_models (model_name, niche, model_type, model_blob,
                feature_names, metrics, training_samples, is_active)
            VALUES ('thumbnail_ctr_predictor', $1, 'gbm_regressor', $2, $3, $4, $5, TRUE)
        """, niche, model_blob, json.dumps(FEATURE_NAMES), json.dumps(metrics), len(rows))

        logger.info("ctr_predictor.trained", niche=niche, r2=mean_r2, samples=len(rows))
        return {"status": "trained", "metrics": metrics}

    except Exception as e:
        logger.error("ctr_predictor.train_failed", error=str(e))
        return {"status": "error", "error": str(e)}
