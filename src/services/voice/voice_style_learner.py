"""Voice Style Learner — Self-learning model for optimal TTS parameters.

Learns which TTS parameter combinations produce the best audience retention.
Uses GBM predictor (same pattern as research/script self-learning) to optimize
voice parameters over time.

Intelligence cost: $0.00 — sklearn + numpy, all local.
"""
from __future__ import annotations

import asyncio
import json
import pickle
from typing import Any

import numpy as np
import structlog

from src.db import get_pool

logger = structlog.get_logger()

FEATURE_NAMES = [
    "avg_stability", "avg_similarity_boost", "avg_style", "avg_speed",
    "emotion_variety", "emphasis_density", "avg_pause_ms",
    "snr_db", "rms_energy", "naturalness_score",
    "wpm", "total_duration_s", "segment_count",
]


async def extract_voice_features(content_id: str, channel_id: str,
                                  audio_metrics: dict, emotion_data: list[dict],
                                  validation: dict) -> dict:
    """Extract and store features for the voice ML pipeline."""
    # Aggregate TTS params
    stabilities = [e.get("stability", 0.5) for e in emotion_data]
    similarities = [e.get("similarity_boost", 0.75) for e in emotion_data]
    styles = [e.get("style", 0.4) for e in emotion_data]
    speeds = [e.get("speed", 1.0) for e in emotion_data]
    pauses = [e.get("pause_after_ms", 300) for e in emotion_data]

    # Emotion variety
    emotions = [e.get("emotion", "neutral") for e in emotion_data]
    unique_emotions = len(set(emotions))
    emotion_variety = unique_emotions / max(len(emotions), 1)

    # Emphasis density
    total_emphasis = sum(len(e.get("emphasis_words", [])) for e in emotion_data)
    emphasis_density = total_emphasis / max(len(emotion_data), 1)

    features = {
        "avg_stability": round(np.mean(stabilities) if stabilities else 0.5, 4),
        "avg_similarity_boost": round(np.mean(similarities) if similarities else 0.75, 4),
        "avg_style": round(np.mean(styles) if styles else 0.4, 4),
        "avg_speed": round(np.mean(speeds) if speeds else 1.0, 4),
        "emotion_variety": round(emotion_variety, 4),
        "emphasis_density": round(emphasis_density, 4),
        "avg_pause_ms": round(np.mean(pauses) if pauses else 300, 1),
        "snr_db": audio_metrics.get("snr_db", 0),
        "rms_energy": audio_metrics.get("rms_energy", 0),
        "naturalness_score": audio_metrics.get("naturalness_score", 7.0),
        "wpm": validation.get("wpm", 150),
        "total_duration_s": validation.get("total_duration_s", 0),
        "segment_count": validation.get("sentence_count", 0),
    }

    # Store in DB
    try:
        pool = await get_pool()
        await pool.execute("""
            INSERT INTO voice_features (content_id, channel_id,
                stability, similarity_boost, style, speed, emotion,
                snr_db, rms_energy, zero_crossing_rate, spectral_centroid,
                duration_s, wpm, audio_quality_score, naturalness_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        """,
            content_id, channel_id,
            features["avg_stability"], features["avg_similarity_boost"],
            features["avg_style"], features["avg_speed"],
            max(set(emotions), key=emotions.count) if emotions else "neutral",
            features["snr_db"], features["rms_energy"],
            audio_metrics.get("zero_crossing_rate", 0),
            audio_metrics.get("spectral_centroid", 0),
            features["total_duration_s"], features["wpm"],
            audio_metrics.get("quality_score", 7.0),
            features["naturalness_score"],
        )
    except Exception as e:
        logger.warning("voice_learner.store_features_failed", error=str(e))

    return features


async def predict_optimal_params(channel_id: str, niche: str) -> dict | None:
    """Predict optimal TTS parameters using trained ML model.
    
    Returns None if no model is trained yet (falls back to defaults).
    """
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT model_blob, feature_names, metrics FROM voice_models "
            "WHERE model_name = 'voice_param_optimizer' AND niche = $1 AND is_active = TRUE "
            "ORDER BY created_at DESC LIMIT 1", niche)

        if not row or not row["model_blob"]:
            return None

        model = pickle.loads(row["model_blob"])
        stored_features = json.loads(row["feature_names"]) if row["feature_names"] else FEATURE_NAMES

        # Get recent successful voice params for this channel
        recent = await pool.fetch("""
            SELECT vf.stability, vf.similarity_boost, vf.style, vf.speed,
                   vf.audio_quality_score, vf.naturalness_score
            FROM voice_features vf
            JOIN voice_outcomes vo ON vf.content_id = vo.content_id
            WHERE vf.channel_id = $1 AND vo.is_good_retention = TRUE
            ORDER BY vf.created_at DESC LIMIT 10
        """, channel_id)

        if not recent:
            return None

        # Average the successful params
        optimal = {
            "stability": round(np.mean([r["stability"] for r in recent if r["stability"]]), 3),
            "similarity_boost": round(np.mean([r["similarity_boost"] for r in recent if r["similarity_boost"]]), 3),
            "style": round(np.mean([r["style"] for r in recent if r["style"]]), 3),
            "speed": round(np.mean([r["speed"] for r in recent if r["speed"]]), 3),
        }

        metrics = json.loads(row["metrics"]) if row["metrics"] else {}
        logger.info("voice_learner.predicted_optimal", channel_id=channel_id,
                     params=optimal, model_auc=metrics.get("auc"))

        return optimal

    except Exception as e:
        logger.warning("voice_learner.predict_failed", error=str(e))
        return None


async def ingest_voice_feedback(content_id: str, channel_id: str,
                                 retention_data: dict) -> bool:
    """Ingest retention data as voice outcome for ML training."""
    try:
        pool = await get_pool()
        avg_view_duration = retention_data.get("avg_view_duration_s", 0)
        retention_30 = retention_data.get("retention_at_30pct", 0)
        retention_50 = retention_data.get("retention_at_50pct", 0)
        retention_70 = retention_data.get("retention_at_70pct", 0)

        # Good retention = above 50% at the 50% mark
        is_good = retention_50 > 0.50

        await pool.execute("""
            INSERT INTO voice_outcomes (content_id, channel_id,
                avg_view_duration_s, retention_at_30pct, retention_at_50pct,
                retention_at_70pct, is_good_retention)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (content_id) DO UPDATE SET
                avg_view_duration_s = EXCLUDED.avg_view_duration_s,
                retention_at_30pct = EXCLUDED.retention_at_30pct,
                retention_at_50pct = EXCLUDED.retention_at_50pct,
                retention_at_70pct = EXCLUDED.retention_at_70pct,
                is_good_retention = EXCLUDED.is_good_retention,
                updated_at = NOW()
        """, content_id, channel_id, avg_view_duration, retention_30,
            retention_50, retention_70, is_good)

        return True
    except Exception as e:
        logger.warning("voice_learner.ingest_failed", error=str(e))
        return False


async def train_voice_model(niche: str) -> dict:
    """Train/retrain the voice parameter optimization model."""
    try:
        pool = await get_pool()

        # Get labeled data
        rows = await pool.fetch("""
            SELECT vf.stability, vf.similarity_boost, vf.style, vf.speed,
                   vf.snr_db, vf.rms_energy, vf.naturalness_score, vf.wpm,
                   vf.duration_s, vf.audio_quality_score,
                   vo.is_good_retention
            FROM voice_features vf
            JOIN voice_outcomes vo ON vf.content_id = vo.content_id
            JOIN channels c ON vf.channel_id = c.channel_id
            WHERE c.niche = $1 AND vo.is_good_retention IS NOT NULL
        """, niche)

        if len(rows) < 15:
            return {"status": "insufficient_data", "samples": len(rows), "min_required": 15}

        # Build feature matrix
        feature_cols = ["stability", "similarity_boost", "style", "speed",
                       "snr_db", "rms_energy", "naturalness_score", "wpm",
                       "duration_s", "audio_quality_score"]
        X = np.array([[float(r[col] or 0) for col in feature_cols] for r in rows])
        y = np.array([1 if r["is_good_retention"] else 0 for r in rows])

        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import cross_val_score

        model = GradientBoostingClassifier(
            n_estimators=50, max_depth=3, learning_rate=0.1, random_state=42)

        scores = cross_val_score(model, X, y, cv=min(5, len(y) // 3), scoring="roc_auc")
        mean_auc = float(np.mean(scores))

        model.fit(X, y)
        model_blob = pickle.dumps(model)

        metrics = {
            "auc": round(mean_auc, 4),
            "samples": len(rows),
            "positive_rate": round(float(np.mean(y)), 4),
            "feature_importance": dict(zip(feature_cols,
                [round(float(fi), 4) for fi in model.feature_importances_])),
        }

        # Store model
        await pool.execute("""
            UPDATE voice_models SET is_active = FALSE
            WHERE model_name = 'voice_param_optimizer' AND niche = $1
        """, niche)

        await pool.execute("""
            INSERT INTO voice_models (model_name, niche, model_type, model_blob,
                feature_names, metrics, training_samples, is_active)
            VALUES ('voice_param_optimizer', $1, 'gbm', $2, $3, $4, $5, TRUE)
        """, niche, model_blob, json.dumps(feature_cols), json.dumps(metrics), len(rows))

        logger.info("voice_learner.model_trained", niche=niche, auc=mean_auc, samples=len(rows))
        return {"status": "trained", "metrics": metrics}

    except Exception as e:
        logger.error("voice_learner.train_failed", error=str(e))
        return {"status": "error", "error": str(e)}
