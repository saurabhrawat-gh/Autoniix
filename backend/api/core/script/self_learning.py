"""Self-Learning Model — Script Intelligence feedback loop.

Learns from actual YouTube performance data to improve script generation:
- GBM classifier: predicts script success from 15+ script features
- Thompson Sampling bandits: hook styles, pacing strategies
- Feedback ingestor: ingests post-publish analytics → labels
- Trainer: retrains weekly with new data
- Drift detection: flags model degradation
- Feature extractor: computes script features for ML training

All computation is local (scikit-learn + numpy). Zero API cost.
"""
from __future__ import annotations

import asyncio
import json
import pickle
from datetime import datetime

import numpy as np
import structlog

from core.db import get_pool

logger = structlog.get_logger()

SCRIPT_FEATURE_NAMES = [
    "segment_count", "word_count", "avg_sentence_length",
    "sentence_length_variance", "hook_strength", "curiosity_loop_count",
    "open_loop_ratio", "pattern_interrupt_freq", "but_therefore_ratio",
    "contraction_rate", "question_density", "specificity_score",
    "readability_score", "emotion_variance", "emphasis_density",
]



async def extract_script_features(
    script_analysis: dict,
    retention_score: dict,
    humanizer_metrics: dict,
    channel_id: str,
    content_id: str,
    topic: str = "",
) -> dict:
    """Extract ML features from script analysis results.

    Combines outputs from script_analyzer, retention_optimizer, and humanizer
    into a flat feature vector for the success predictor.
    """
    dims = retention_score.get("dimensions", {})
    details = retention_score.get("details", {})

    features = {
        "segment_count": script_analysis.get("segment_analyses", []) and len(script_analysis.get("segment_analyses", [])),
        "word_count": script_analysis.get("total_word_count", 0),
        "avg_sentence_length": script_analysis.get("avg_sentence_length", 0),
        "sentence_length_variance": script_analysis.get("sentence_length_variance", 0),
        "hook_strength": dims.get("hook_strength", 0),
        "curiosity_loop_count": details.get("curiosity", {}).get("loop_count", 0),
        "open_loop_ratio": details.get("curiosity", {}).get("close_ratio", 0),
        "pattern_interrupt_freq": details.get("pattern_interrupts", {}).get("frequency_per_1k", 0),
        "but_therefore_ratio": details.get("but_therefore", {}).get("ratio", 0),
        "contraction_rate": humanizer_metrics.get("contraction_rate", 0),
        "question_density": script_analysis.get("overall_question_density", 0),
        "specificity_score": script_analysis.get("overall_specificity", 0),
        "readability_score": script_analysis.get("overall_readability", {}).get("flesch_reading_ease", 50) / 100,
        "emotion_variance": script_analysis.get("emotion_arc_variance", 0),
        "emphasis_density": sum(
            len(sa.get("emphasis_words", []))
            for sa in script_analysis.get("segment_analyses", [])
        ) / max(script_analysis.get("total_word_count", 1), 1),
    }

    return features


async def store_script_features(
    content_id: str,
    channel_id: str,
    features: dict,
    overall_score: float = 0,
    hook_score: float = 0,
    hook_style: str = "",
    pacing_strategy: str = "",
    topic: str = "",
) -> None:
    """Store script features in DB for ML training."""
    pool = await get_pool()
    try:
        await pool.execute("""
            INSERT INTO script_features (
                content_id, channel_id, topic,
                segment_count, word_count, avg_sentence_length,
                sentence_length_variance, hook_strength, curiosity_loop_count,
                open_loop_ratio, pattern_interrupt_freq, but_therefore_ratio,
                contraction_rate, question_density, specificity_score,
                readability_score, emotion_variance, emphasis_density,
                emotional_arc_score, overall_script_score, hook_retention_score,
                hook_style_used, pacing_strategy_used
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
            )
        """,
            content_id, channel_id, topic,
            features.get("segment_count", 0),
            features.get("word_count", 0),
            features.get("avg_sentence_length", 0),
            features.get("sentence_length_variance", 0),
            features.get("hook_strength", 0),
            features.get("curiosity_loop_count", 0),
            features.get("open_loop_ratio", 0),
            features.get("pattern_interrupt_freq", 0),
            features.get("but_therefore_ratio", 0),
            features.get("contraction_rate", 0),
            features.get("question_density", 0),
            features.get("specificity_score", 0),
            features.get("readability_score", 0),
            features.get("emotion_variance", 0),
            features.get("emphasis_density", 0),
            0.0,
            overall_score,
            hook_score,
            hook_style,
            pacing_strategy,
        )
        logger.info("script_features.stored", content_id=content_id)
    except Exception as e:
        logger.warning("script_features.store_failed", content_id=content_id, error=str(e))



async def _load_model(model_name: str, niche: str | None = None):
    """Load the latest trained model from DB."""
    pool = await get_pool()
    query = """
        SELECT model_blob, feature_names, metrics FROM script_models
        WHERE model_name = $1 AND is_active = TRUE
    """
    params = [model_name]
    if niche:
        query += " AND niche = $2"
        params.append(niche)
    query += " ORDER BY model_version DESC LIMIT 1"

    row = await pool.fetchrow(query, *params)
    if not row or not row["model_blob"]:
        return None, None

    model = pickle.loads(row["model_blob"])
    metrics = json.loads(row["metrics"]) if isinstance(row["metrics"], str) else row["metrics"]
    return model, metrics


async def predict_script_success(features: dict, niche: str | None = None) -> dict:
    """Predict probability of script success from features.

    Falls back to weighted rule-based scoring if no model trained yet.
    """
    model, metrics = await _load_model("script_success_predictor", niche)

    if model is None:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT config_value FROM system_config WHERE config_key = 'script_feature_weights'"
        )
        weights = {}
        if row:
            try:
                weights = json.loads(row["config_value"])
            except (json.JSONDecodeError, TypeError):
                pass

        if not weights:
            weights = {
                "hook_strength": 0.18, "curiosity_loops": 0.12,
                "pattern_interrupts": 0.10, "but_therefore": 0.08,
                "specificity": 0.12, "emotion_variance": 0.10,
                "readability": 0.08, "contraction_rate": 0.07,
                "question_density": 0.08, "pacing_score": 0.07,
            }

        feature_map = {
            "hook_strength": features.get("hook_strength", 0.5),
            "curiosity_loops": min(1.0, features.get("curiosity_loop_count", 0) / 5),
            "pattern_interrupts": min(1.0, features.get("pattern_interrupt_freq", 0) / 30),
            "but_therefore": features.get("but_therefore_ratio", 0.5),
            "specificity": features.get("specificity_score", 0.5),
            "emotion_variance": min(1.0, features.get("emotion_variance", 0) * 5),
            "readability": features.get("readability_score", 0.5),
            "contraction_rate": min(1.0, features.get("contraction_rate", 0) * 20),
            "question_density": min(1.0, features.get("question_density", 0) * 5),
            "pacing_score": 0.5,
        }

        score = sum(feature_map.get(k, 0.5) * w for k, w in weights.items())
        return {
            "predicted_probability": round(score, 4),
            "model_type": "rule_based",
            "confidence": 0.3,
            "note": "No trained model yet; using weighted feature scoring.",
        }

    X = np.array([[features.get(f, 0.0) for f in SCRIPT_FEATURE_NAMES]])

    def _predict():
        prob = model.predict_proba(X)[0]
        return float(prob[1]) if len(prob) > 1 else float(prob[0])

    predicted = await asyncio.to_thread(_predict)

    return {
        "predicted_probability": round(predicted, 4),
        "model_type": "gradient_boosted",
        "confidence": round(float(metrics.get("roc_auc", 0.5)), 3),
        "training_samples": int(metrics.get("n_samples", 0)),
    }



async def thompson_sample(
    niche: str,
    bandit_type: str,
    arms: list[str],
    *,
    channel_id: str | None = None,
) -> dict:
    """Select an arm using Thompson Sampling, with diversity floor.

    bandit_type: "hook_style" or "pacing_strategy"
    arms: list of arm names
    channel_id: optional. When provided, the Phase 10 diversity floor
        checks this channel's recent picks for the same bandit_type
        and overrides Thompson with the least-pulled arm if entropy
        of recent picks is below threshold. Without it, behaviour is
        identical to pure Thompson sampling — useful for tests.
    """
    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT arm_name, alpha, beta, pulls, rewards
        FROM script_bandit_state
        WHERE niche = $1 AND bandit_type = $2
    """, niche, bandit_type)

    arm_states = {r["arm_name"]: dict(r) for r in rows}

    for arm in arms:
        if arm not in arm_states:
            await pool.execute("""
                INSERT INTO script_bandit_state (niche, bandit_type, arm_name, alpha, beta, pulls, rewards)
                VALUES ($1, $2, $3, 1, 1, 0, 0)
                ON CONFLICT (niche, bandit_type, arm_name) DO NOTHING
            """, niche, bandit_type, arm)
            arm_states[arm] = {"alpha": 1.0, "beta": 1.0, "pulls": 0, "rewards": 0.0}

    samples = {}
    for arm in arms:
        state = arm_states.get(arm, {"alpha": 1.0, "beta": 1.0})
        a = float(state["alpha"])
        b = float(state["beta"])
        samples[arm] = float(np.random.beta(a, b))

    thompson_pick = max(samples, key=samples.get)

    forced_exploration = False
    entropy = None
    selected = thompson_pick
    if channel_id:
        try:
            from intelligence.diversity_floor import evaluate_diversity_floor
            decision = await evaluate_diversity_floor(
                channel_id=channel_id,
                bandit_type=bandit_type,
                available_arms=arms,
            )
            entropy = decision["entropy"]
            if decision["force"] and decision["forced_arm"]:
                selected = decision["forced_arm"]
                forced_exploration = True
                logger.info("script_bandit.diversity_override",
                            niche=niche, type=bandit_type,
                            channel_id=channel_id, entropy=entropy,
                            thompson_pick=thompson_pick,
                            forced_pick=selected)
        except Exception as exc:
            logger.warning("script_bandit.diversity_check_failed",
                           niche=niche, type=bandit_type, error=str(exc))

    if channel_id:
        try:
            from intelligence.diversity_floor import log_bandit_pick
            await log_bandit_pick(
                niche=niche, bandit_type=bandit_type,
                channel_id=channel_id, arm_name=selected,
                forced_exploration=forced_exploration,
            )
        except Exception:
            pass

    exploration = 1.0 / (1 + arm_states.get(selected, {}).get("pulls", 0))

    logger.info("script_bandit.sampled", niche=niche, type=bandit_type,
                selected=selected,
                pulls=arm_states.get(selected, {}).get("pulls", 0),
                forced=forced_exploration)

    return {
        "selected_arm": selected,
        "sampled_value": round(samples[selected], 4),
        "all_samples": {k: round(v, 4) for k, v in samples.items()},
        "exploration_bonus": round(exploration, 4),
        "forced_exploration": forced_exploration,
        "entropy": entropy,
    }


async def bandit_update(niche: str, bandit_type: str, arm: str, reward: float) -> None:
    """Update bandit arm after observing outcome."""
    pool = await get_pool()
    await pool.execute("""
        UPDATE script_bandit_state SET
            alpha = alpha + $1,
            beta = beta + (1 - $1),
            pulls = pulls + 1,
            rewards = rewards + $1,
            avg_reward = CASE WHEN pulls > 0 THEN (rewards + $1) / (pulls + 1) ELSE $1 END,
            updated_at = NOW()
        WHERE niche = $2 AND bandit_type = $3 AND arm_name = $4
    """, reward, niche, bandit_type, arm)

    logger.info("script_bandit.updated", niche=niche, type=bandit_type, arm=arm, reward=round(reward, 3))



async def ingest_script_performance(content_id: str, analytics: dict) -> dict:
    """Ingest post-publish YouTube analytics and compute success label.

    Focuses on retention-relevant metrics: avg_view_pct, early drop-off,
    engagement rate.
    """
    pool = await get_pool()

    views_48h = analytics.get("views_48h", 0)
    ctr = analytics.get("ctr", 0.0)
    avg_view_pct = analytics.get("avg_view_pct", 0.0)
    avg_view_duration = analytics.get("avg_view_duration_s", 0.0)
    likes = analytics.get("likes", 0)
    comments = analytics.get("comments", 0)
    retention_curve = analytics.get("retention_curve", [])

    views = max(views_48h, 1)
    engagement = min(1.0, (likes + comments * 2) / views)

    score = 0
    if avg_view_pct >= 0.55:
        score += 4
    elif avg_view_pct >= 0.40:
        score += 2
    elif avg_view_pct >= 0.30:
        score += 1

    if ctr >= 0.08:
        score += 2
    elif ctr >= 0.05:
        score += 1

    if engagement >= 0.05:
        score += 2
    elif engagement >= 0.02:
        score += 1

    if score >= 6:
        tier, is_success = "viral", True
    elif score >= 4:
        tier, is_success = "strong", True
    elif score >= 2:
        tier, is_success = "average", False
    else:
        tier, is_success = "weak", False

    feat_row = await pool.fetchrow("""
        SELECT hook_style_used, pacing_strategy_used FROM script_features WHERE content_id = $1
    """, content_id)
    hook_style = feat_row["hook_style_used"] if feat_row else None
    pacing_strategy = feat_row["pacing_strategy_used"] if feat_row else None

    try:
        await pool.execute("""
            INSERT INTO script_outcomes (
                content_id, channel_id, yt_video_id,
                impressions, views_48h, ctr, avg_view_pct, avg_view_duration_s,
                likes, comments, retention_curve, engagement_rate,
                is_success, success_tier, hook_style_used, pacing_strategy_used, fetched_at
            ) VALUES (
                $1,
                (SELECT channel_id FROM videos WHERE content_id = $1),
                $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13, $14, $15, NOW()
            )
            ON CONFLICT (content_id) DO UPDATE SET
                views_48h = EXCLUDED.views_48h,
                ctr = EXCLUDED.ctr,
                avg_view_pct = EXCLUDED.avg_view_pct,
                avg_view_duration_s = EXCLUDED.avg_view_duration_s,
                likes = EXCLUDED.likes,
                comments = EXCLUDED.comments,
                retention_curve = EXCLUDED.retention_curve,
                engagement_rate = EXCLUDED.engagement_rate,
                is_success = EXCLUDED.is_success,
                success_tier = EXCLUDED.success_tier,
                fetched_at = NOW(),
                updated_at = NOW()
        """,
            content_id, analytics.get("yt_video_id"),
            analytics.get("impressions", 0), views_48h, ctr, avg_view_pct,
            avg_view_duration, likes, comments,
            json.dumps(retention_curve), engagement, is_success, tier,
            hook_style, pacing_strategy,
        )
    except Exception as e:
        logger.warning("script_feedback.store_failed", content_id=content_id, error=str(e))

    ch_row = await pool.fetchrow("""
        SELECT c.niche FROM videos v JOIN channels c ON v.channel_id = c.channel_id
        WHERE v.content_id = $1
    """, content_id)
    if ch_row:
        niche = ch_row["niche"]
        reward = 1.0 if is_success else 0.0
        if hook_style:
            await bandit_update(niche, "hook_style", hook_style, reward)
        if pacing_strategy:
            await bandit_update(niche, "pacing_strategy", pacing_strategy, reward)

    result = {
        "is_success": is_success,
        "success_tier": tier,
        "engagement_rate": round(engagement, 4),
        "score": score,
    }
    logger.info("script_feedback.ingested", content_id=content_id, tier=tier, score=score)
    return result



async def train_model(niche: str | None = None, min_samples: int = 15) -> dict:
    """Train/retrain the GBM script success predictor.

    Joins script_features (X) with script_outcomes (y).
    Uses GradientBoostingClassifier with isotonic calibration.
    """
    pool = await get_pool()

    query = """
        SELECT sf.*, so.is_success
        FROM script_features sf
        JOIN script_outcomes so ON sf.content_id = so.content_id
        WHERE so.is_success IS NOT NULL
    """
    params = []
    if niche:
        query += " AND sf.channel_id IN (SELECT channel_id FROM channels WHERE niche = $1)"
        params.append(niche)

    rows = await pool.fetch(query, *params)

    if len(rows) < min_samples:
        return {
            "status": "insufficient_data",
            "samples_available": len(rows),
            "min_required": min_samples,
        }

    X = np.array([
        [float(row.get(f, 0) or 0) for f in SCRIPT_FEATURE_NAMES]
        for row in rows
    ])
    y = np.array([1 if row["is_success"] else 0 for row in rows])

    def _train():
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.model_selection import cross_val_score

        base = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        )

        cv_scores = cross_val_score(base, X, y, cv=min(5, len(y) // 3), scoring="roc_auc")
        avg_auc = float(np.mean(cv_scores))

        base.fit(X, y)
        calibrated = CalibratedClassifierCV(base, method="isotonic", cv=3)
        calibrated.fit(X, y)

        importances = dict(zip(SCRIPT_FEATURE_NAMES, base.feature_importances_.tolist()))

        return calibrated, avg_auc, importances

    model, auc, importances = await asyncio.to_thread(_train)

    model_blob = pickle.dumps(model)
    current_version = await pool.fetchval("""
        SELECT COALESCE(MAX(model_version), 0) + 1 FROM script_models
        WHERE model_name = 'script_success_predictor' AND niche = $1
    """, niche or "__global__")

    await pool.execute("""
        UPDATE script_models SET is_active = FALSE
        WHERE model_name = 'script_success_predictor' AND niche = $1
    """, niche or "__global__")

    await pool.execute("""
        INSERT INTO script_models (model_name, model_version, niche, model_type, model_blob,
                                   feature_names, metrics, training_samples, is_active)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, TRUE)
    """,
        "script_success_predictor", current_version, niche or "__global__",
        "gradient_boosted_calibrated", model_blob,
        json.dumps(SCRIPT_FEATURE_NAMES),
        json.dumps({"roc_auc": auc, "n_samples": len(rows), "importances": importances}),
        len(rows),
    )

    result = {
        "status": "trained",
        "model_version": current_version,
        "niche": niche or "__global__",
        "roc_auc": round(auc, 4),
        "training_samples": len(rows),
        "feature_importances": {k: round(v, 4) for k, v in importances.items()},
    }
    logger.info("script_model.trained", **result)
    return result



async def detect_drift(niche: str | None = None) -> dict:
    """Check if the current model is still performing well.

    Compares recent predictions to actual outcomes.
    """
    model, metrics = await _load_model("script_success_predictor", niche)
    if model is None:
        return {"status": "no_model", "needs_retrain": False}

    pool = await get_pool()

    rows = await pool.fetch("""
        SELECT sf.*, so.is_success
        FROM script_features sf
        JOIN script_outcomes so ON sf.content_id = so.content_id
        WHERE so.is_success IS NOT NULL
        AND so.created_at > (SELECT COALESCE(MAX(created_at), '2000-01-01') FROM script_models
                             WHERE model_name = 'script_success_predictor' AND is_active = TRUE)
    """)

    if len(rows) < 5:
        return {"status": "insufficient_recent_data", "samples": len(rows), "needs_retrain": False}

    X = np.array([[float(row.get(f, 0) or 0) for f in SCRIPT_FEATURE_NAMES] for row in rows])
    y_true = np.array([1 if row["is_success"] else 0 for row in rows])

    def _evaluate():
        from sklearn.metrics import roc_auc_score
        y_pred = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else model.predict(X)
        try:
            return float(roc_auc_score(y_true, y_pred))
        except ValueError:
            return 0.5

    recent_auc = await asyncio.to_thread(_evaluate)
    original_auc = float(metrics.get("roc_auc", 0.5)) if metrics else 0.5

    threshold_row = await pool.fetchrow(
        "SELECT config_value FROM system_config WHERE config_key = 'script_ml_drift_auc_threshold'"
    )
    threshold = float(threshold_row["config_value"]) if threshold_row else 0.55

    needs_retrain = recent_auc < threshold

    result = {
        "status": "evaluated",
        "original_auc": round(original_auc, 4),
        "recent_auc": round(recent_auc, 4),
        "drift_threshold": threshold,
        "needs_retrain": needs_retrain,
        "recent_samples": len(rows),
    }
    logger.info("script_drift.checked", **result)
    return result
