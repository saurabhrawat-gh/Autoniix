"""Self-Learning Model — GBM predictor + Thompson Sampling bandit + feedback loop.

Learns from actual YouTube performance data to improve topic selection.
- GBM classifier: predicts "success" from research features.
- Thompson Sampling bandit: balances exploration vs exploitation across topic clusters.
- Feedback ingestor: pulls post-publish analytics and writes training labels.
- Trainer: retrains weekly with new data; updates model + opportunity weights.

All computation is local (scikit-learn + numpy). Zero API cost.
"""
from __future__ import annotations

import asyncio
import io
import json
import pickle
from datetime import datetime, timedelta

import numpy as np
import structlog

from src.db import get_pool

logger = structlog.get_logger()

FEATURE_NAMES = [
    "freshness_score", "novelty_score", "trend_momentum",
    "supply_demand_gap", "hookability_score", "competitor_gap",
    "burst_score", "seasonality_score", "phrase_novelty",
]


# GBM PREDICTOR

async def _load_model(niche: str | None = None):
    """Load the latest trained model from DB."""
    pool = await get_pool()
    query = """
        SELECT model_blob, feature_names, metrics FROM ml_models
        WHERE model_name = 'topic_success_predictor' AND is_active = TRUE
    """
    params = []
    if niche:
        query += " AND niche = $1"
        params.append(niche)
    query += " ORDER BY model_version DESC LIMIT 1"

    row = await pool.fetchrow(query, *params)
    if not row or not row["model_blob"]:
        return None, None

    model = pickle.loads(row["model_blob"])
    metrics = json.loads(row["metrics"]) if isinstance(row["metrics"], str) else row["metrics"]
    return model, metrics


async def predict_success(
    features: dict,
    niche: str | None = None,
    *,
    content_id: str | None = None,
) -> dict:
    """Predict probability of success for a topic given its features.

    Phase 11: when ``content_id`` is provided we log the prediction +
    confidence to ``prediction_log``. The feedback ingestor later
    fills in the actual outcome and computes ``sample_weight`` so
    the next training pass biases toward high-confidence misses.

    ``content_id`` is optional for backward compatibility; without it
    no logging occurs and behaviour matches the pre-Phase-11 path.

    Rule-based fallback predictions are deliberately *not* logged —
    they carry no model signal so weighting them in retraining would
    be meaningless. Once the model has trained even once, every
    subsequent call is logged.

    Returns:
        dict with predicted_probability, model_version, confidence.
        Falls back to rule-based scoring if no model trained yet.
    """
    model, metrics = await _load_model(niche)

    if model is None:
        # No trained model yet — return rule-based estimate
        vals = [features.get(f, 0.5) for f in FEATURE_NAMES]
        rule_score = sum(vals) / len(vals)
        return {
            "predicted_probability": round(rule_score, 4),
            "model_type": "rule_based",
            "confidence": 0.3,
            "note": "No trained model yet; using feature average.",
        }

    # Build feature vector
    X = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])

    def _predict():
        prob = model.predict_proba(X)[0]
        # prob[1] = P(success)
        return float(prob[1]) if len(prob) > 1 else float(prob[0])

    predicted = await asyncio.to_thread(_predict)
    confidence = float(metrics.get("roc_auc", 0.5))

    # Phase 11 — audit-log the prediction for the calibration loop.
    # Best-effort; log_prediction itself swallows DB errors so this
    # never blocks the prediction path.
    if content_id:
        try:
            from src.intelligence.prediction_calibration import log_prediction
            await log_prediction(
                content_id=content_id,
                model_kind="topic_success",
                niche=niche,
                predicted_prob=predicted,
                confidence=confidence,
                model_version=int(metrics.get("model_version", 0)) or None,
            )
        except Exception as exc:
            logger.warning("predict.log_failed", content_id=content_id, error=str(exc))

    return {
        "predicted_probability": round(predicted, 4),
        "model_type": "gradient_boosted",
        "confidence": round(confidence, 3),
        "training_samples": int(metrics.get("n_samples", 0)),
    }


# THOMPSON SAMPLING BANDIT

async def thompson_sample(
    niche: str,
    arms: list[str],
    *,
    channel_id: str | None = None,
) -> dict:
    """Select a topic cluster using Thompson Sampling, with diversity floor.

    Each arm = a topic cluster/angle. Maintains Beta(alpha, beta)
    priors updated by success/failure outcomes.

    Phase 10 (anti-mode-collapse): before sampling, the diversity floor
    inspects this channel's recent picks for ``topic_cluster``. If the
    Shannon entropy of recent arm selections is below threshold the
    Thompson sample is overridden with the least-pulled arm — a hard
    exploration nudge. Either way the resulting pick is logged to
    ``bandit_picks`` for future diversity calls.

    ``channel_id`` is optional for backward compatibility: callers that
    don't pass it skip the diversity check entirely (useful for tests
    and any code path that genuinely wants pure Thompson).

    Returns:
        dict with selected_arm, sampled_value, exploration_bonus,
        forced_exploration (Phase 10), entropy (Phase 10).
    """
    pool = await get_pool()

    # Load or initialize arms
    rows = await pool.fetch("""
        SELECT arm_name, alpha, beta, pulls, rewards FROM bandit_state WHERE niche = $1
    """, niche)

    arm_states = {r["arm_name"]: dict(r) for r in rows}

    # Initialize missing arms
    for arm in arms:
        if arm not in arm_states:
            await pool.execute("""
                INSERT INTO bandit_state (niche, arm_name, alpha, beta, pulls, rewards)
                VALUES ($1, $2, 1, 1, 0, 0)
                ON CONFLICT (niche, arm_name) DO NOTHING
            """, niche, arm)
            arm_states[arm] = {"alpha": 1.0, "beta": 1.0, "pulls": 0, "rewards": 0.0}

    # Sample from Beta distribution for each arm
    samples = {}
    for arm in arms:
        state = arm_states.get(arm, {"alpha": 1.0, "beta": 1.0})
        a = float(state["alpha"])
        b = float(state["beta"])
        samples[arm] = float(np.random.beta(a, b))

    # Thompson selection.
    thompson_pick = max(samples, key=samples.get)

    # Phase 10 — diversity floor check. Cold-start safe: returns
    # force=False on missing channel_id, empty history, or DB error.
    forced_exploration = False
    entropy = None
    selected = thompson_pick
    if channel_id:
        try:
            from src.intelligence.diversity_floor import evaluate_diversity_floor
            decision = await evaluate_diversity_floor(
                channel_id=channel_id,
                bandit_type="topic_cluster",
                available_arms=arms,
            )
            entropy = decision["entropy"]
            if decision["force"] and decision["forced_arm"]:
                selected = decision["forced_arm"]
                forced_exploration = True
                logger.info("bandit.diversity_override",
                            niche=niche, channel_id=channel_id,
                            entropy=entropy,
                            thompson_pick=thompson_pick,
                            forced_pick=selected)
        except Exception as exc:
            logger.warning("bandit.diversity_check_failed",
                           niche=niche, error=str(exc))

    # Audit-log the pick (always, regardless of whether floor fired) so
    # the next call has data to compute entropy from.
    if channel_id:
        try:
            from src.intelligence.diversity_floor import log_bandit_pick
            await log_bandit_pick(
                niche=niche, bandit_type="topic_cluster",
                channel_id=channel_id, arm_name=selected,
                forced_exploration=forced_exploration,
            )
        except Exception:
            pass  # log_bandit_pick already logs on failure

    exploration = 1.0 / (1 + arm_states.get(selected, {}).get("pulls", 0))

    result = {
        "selected_arm": selected,
        "sampled_value": round(samples[selected], 4),
        "all_samples": {k: round(v, 4) for k, v in samples.items()},
        "exploration_bonus": round(exploration, 4),
        # Phase 10 fields. ``forced_exploration`` is the canonical
        # signal that the diversity floor fired this round.
        "forced_exploration": forced_exploration,
        "entropy": entropy,
    }

    logger.info("bandit.sampled", niche=niche, selected=selected,
                value=round(samples[selected], 3),
                pulls=arm_states.get(selected, {}).get("pulls", 0),
                forced=forced_exploration)
    return result


async def bandit_update(niche: str, arm: str, reward: float) -> None:
    """Update bandit arm after observing outcome.

    reward: 1.0 = success, 0.0 = failure, or continuous in [0,1].
    """
    pool = await get_pool()
    await pool.execute("""
        UPDATE bandit_state SET
            alpha = alpha + $1,
            beta = beta + (1 - $1),
            pulls = pulls + 1,
            rewards = rewards + $1,
            updated_at = NOW()
        WHERE niche = $2 AND arm_name = $3
    """, reward, niche, arm)

    logger.info("bandit.updated", niche=niche, arm=arm, reward=round(reward, 3))


# FEEDBACK INGESTOR

async def ingest_performance(content_id: str, analytics: dict) -> dict:
    """Ingest post-publish YouTube analytics and compute success label.

    Args:
        content_id: Our internal video content_id.
        analytics: Dict with views_24h, views_48h, ctr, avg_view_duration, etc.

    Returns:
        dict with is_success, success_tier, engagement_rate.
    """
    pool = await get_pool()

    views_24h = analytics.get("views_24h", 0)
    views_48h = analytics.get("views_48h", 0)
    ctr = analytics.get("ctr", 0.0)
    avd = analytics.get("avg_view_duration", 0.0)
    avg_pct = analytics.get("avg_view_pct", 0.0)
    likes = analytics.get("likes", 0)
    comments = analytics.get("comments", 0)
    subs_gained = analytics.get("subs_gained", 0)

    # Compute engagement rate
    views = max(views_48h, views_24h, 1)
    engagement = (likes + comments * 2 + subs_gained * 5) / views
    engagement = round(min(1.0, engagement), 4)

    # Determine success tier
    # Use CTR (good > 0.06), AVD% (good > 0.40), and view velocity
    score = 0
    if ctr >= 0.08:
        score += 3
    elif ctr >= 0.05:
        score += 1
    if avg_pct >= 0.50:
        score += 3
    elif avg_pct >= 0.35:
        score += 1
    if views_48h >= 1000:
        score += 2
    elif views_48h >= 200:
        score += 1

    if score >= 6:
        tier = "viral"
        is_success = True
    elif score >= 4:
        tier = "strong"
        is_success = True
    elif score >= 2:
        tier = "average"
        is_success = False
    else:
        tier = "weak"
        is_success = False

    # Store
    try:
        await pool.execute("""
            INSERT INTO performance_outcomes
                (content_id, channel_id, yt_video_id, impressions,
                 views_24h, views_48h, views_7d, ctr, avg_view_duration,
                 avg_view_pct, likes, comments, subs_gained,
                 engagement_rate, is_success, success_tier, fetched_at)
            VALUES (
                $1,
                (SELECT channel_id FROM videos WHERE content_id = $1),
                $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW()
            )
            ON CONFLICT (content_id) DO UPDATE SET
                views_24h = EXCLUDED.views_24h,
                views_48h = EXCLUDED.views_48h,
                views_7d = EXCLUDED.views_7d,
                ctr = EXCLUDED.ctr,
                avg_view_duration = EXCLUDED.avg_view_duration,
                avg_view_pct = EXCLUDED.avg_view_pct,
                likes = EXCLUDED.likes,
                comments = EXCLUDED.comments,
                subs_gained = EXCLUDED.subs_gained,
                engagement_rate = EXCLUDED.engagement_rate,
                is_success = EXCLUDED.is_success,
                success_tier = EXCLUDED.success_tier,
                fetched_at = NOW(),
                updated_at = NOW()
        """,
            content_id, analytics.get("yt_video_id"),
            analytics.get("impressions", 0), views_24h, views_48h,
            analytics.get("views_7d", 0), ctr, avd, avg_pct,
            likes, comments, subs_gained, engagement, is_success, tier,
        )
    except Exception as e:
        logger.warning("feedback.store_failed", content_id=content_id, error=str(e))

    # Also update bandit if we have the arm info
    feat_row = await pool.fetchrow("""
        SELECT bandit_arm, channel_id FROM research_features WHERE content_id = $1
    """, content_id)
    if feat_row and feat_row["bandit_arm"]:
        ch_row = await pool.fetchrow("SELECT niche FROM channels WHERE channel_id = $1", feat_row["channel_id"])
        if ch_row:
            reward = 1.0 if is_success else 0.0
            await bandit_update(ch_row["niche"], feat_row["bandit_arm"], reward)

    # Phase 11 — close the prediction-error loop. The actual outcome
    # is now known; reach back into prediction_log, compute abs_error
    # and sample_weight, and stamp them on the row. The next training
    # run picks these up via LEFT JOIN. No-op when there's no logged
    # prediction (e.g. rule-based fallback skipped logging by design).
    try:
        from src.intelligence.prediction_calibration import update_prediction_actual
        await update_prediction_actual(
            content_id=content_id,
            model_kind="topic_success",
            actual_outcome=1.0 if is_success else 0.0,
        )
    except Exception as exc:
        logger.warning("feedback.calibration_update_failed",
                       content_id=content_id, error=str(exc))

    result = {
        "is_success": is_success,
        "success_tier": tier,
        "engagement_rate": engagement,
        "score": score,
    }

    logger.info("feedback.ingested", content_id=content_id, tier=tier, score=score)
    return result


# MODEL TRAINER

async def train_model(niche: str | None = None, min_samples: int = 20) -> dict:
    """Train/retrain the GBM topic success predictor.

    Joins research_features (X) with performance_outcomes (y) to build
    a supervised dataset. Uses GradientBoostingClassifier with
    isotonic calibration.

    Args:
        niche: Train niche-specific model (None = global).
        min_samples: Minimum labeled samples required to train.

    Returns:
        dict with status, metrics, feature_importances.
    """
    pool = await get_pool()

    # Build training set.
    # Phase 11: LEFT JOIN against prediction_log so we can pull the
    # confidence-weighted sample_weight per row. NULL coalesces to 1.0
    # so unscored rows (rule-based predictions, predictions never
    # back-filled) train at uniform weight — never zeroed out.
    query = """
        SELECT rf.freshness_score, rf.novelty_score, rf.trend_momentum,
               rf.supply_demand_gap, rf.hookability_score, rf.competitor_gap,
               rf.burst_score, rf.seasonality_score, rf.phrase_novelty,
               po.is_success,
               COALESCE(pl.sample_weight, 1.0)::float AS sample_weight
        FROM      research_features rf
        JOIN      performance_outcomes po ON rf.content_id = po.content_id
        LEFT JOIN prediction_log       pl ON pl.content_id = rf.content_id
                                         AND pl.model_kind = 'topic_success'
        WHERE po.is_success IS NOT NULL
    """
    params = []
    if niche:
        query += " AND rf.channel_id IN (SELECT channel_id FROM channels WHERE niche = $1)"
        params.append(niche)

    rows = await pool.fetch(query, *params)

    if len(rows) < min_samples:
        return {
            "status": "insufficient_data",
            "samples": len(rows),
            "min_required": min_samples,
        }

    # Build numpy arrays
    X = np.array([[float(r[f]) for f in FEATURE_NAMES] for r in rows])
    y = np.array([1 if r["is_success"] else 0 for r in rows])
    # Phase 11: per-sample weights from the calibration loop.
    sample_weights = np.array([float(r["sample_weight"]) for r in rows])
    n_weighted = int((sample_weights > 1.0).sum())

    def _train():
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.model_selection import cross_val_score
        from sklearn.metrics import roc_auc_score

        # Train with cross-validation
        base_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        )

        # CV scores. Note: cross_val_score does *not* take sample_weight
        # in older sklearn versions, so we run unweighted CV for a
        # stable benchmark and reserve sample_weight for the final fit.
        # This is intentional — CV measures the model's intrinsic
        # ability on this data; sample_weight is a *training* hint, not
        # a *measurement* hint.
        cv_scores = cross_val_score(base_model, X, y, cv=min(5, len(y) // 4), scoring="roc_auc")

        # Train final model with isotonic calibration. Pass
        # sample_weight to .fit() so high-confidence misses (Phase 11)
        # pull the gradient harder than uniform retraining would.
        base_model.fit(X, y, sample_weight=sample_weights)
        cal_model = CalibratedClassifierCV(base_model, cv=3, method="isotonic")
        # CalibratedClassifierCV.fit also accepts sample_weight — keep
        # them aligned so the calibration layer doesn't undo what the
        # base model just learned.
        cal_model.fit(X, y, sample_weight=sample_weights)

        # Feature importances from base model
        importances = dict(zip(FEATURE_NAMES, base_model.feature_importances_.tolist()))

        # Derive updated opportunity weights from importances
        total_imp = sum(base_model.feature_importances_)
        if total_imp > 0:
            new_weights = {
                f: round(imp / total_imp, 4)
                for f, imp in zip(FEATURE_NAMES, base_model.feature_importances_)
            }
        else:
            new_weights = None

        return cal_model, {
            "roc_auc": round(float(cv_scores.mean()), 4),
            "roc_auc_std": round(float(cv_scores.std()), 4),
            "n_samples": len(y),
            "positive_rate": round(float(y.mean()), 4),
            "feature_importances": importances,
            "weights": new_weights,
            # Phase 11 — visibility into how aggressively the
            # calibration loop is steering this training run.
            "n_weighted_samples":   n_weighted,
            "weighted_fraction":    round(n_weighted / len(y), 4) if len(y) else 0.0,
            "mean_sample_weight":   round(float(sample_weights.mean()), 3),
            "max_sample_weight":    round(float(sample_weights.max()), 3),
        }

    model, metrics = await asyncio.to_thread(_train)

    # Serialize and store
    model_blob = pickle.dumps(model)

    # Get next version
    version_row = await pool.fetchrow("""
        SELECT COALESCE(MAX(model_version), 0) + 1 AS next_v FROM ml_models
        WHERE model_name = 'topic_success_predictor' AND niche = $1
    """, niche or "__global__")
    next_version = version_row["next_v"]

    # Deactivate old versions
    await pool.execute("""
        UPDATE ml_models SET is_active = FALSE
        WHERE model_name = 'topic_success_predictor' AND niche = $1
    """, niche or "__global__")

    # Insert new model
    await pool.execute("""
        INSERT INTO ml_models (model_name, model_version, niche, model_type,
            model_blob, feature_names, metrics, training_samples, is_active)
        VALUES ($1, $2, $3, 'gradient_boosted', $4, $5, $6, $7, TRUE)
    """,
        "topic_success_predictor", next_version, niche or "__global__",
        model_blob, json.dumps(FEATURE_NAMES), json.dumps(metrics),
        len(rows),
    )

    # Also store updated opportunity weights if learned
    if metrics.get("weights"):
        await pool.execute("""
            INSERT INTO ml_models (model_name, model_version, niche, model_type,
                feature_names, metrics, is_active)
            VALUES ('opportunity_weights', $1, $2, 'weight_vector', '[]', $3, TRUE)
            ON CONFLICT (model_name, niche, model_version) DO UPDATE SET
                metrics = EXCLUDED.metrics, is_active = TRUE
        """, next_version, niche or "__global__", json.dumps({"weights": metrics["weights"]}))

    logger.info("trainer.completed",
                niche=niche, version=next_version,
                auc=metrics["roc_auc"], samples=len(rows),
                importances=metrics["feature_importances"])

    return {
        "status": "trained",
        "model_version": next_version,
        "metrics": metrics,
    }


# DRIFT DETECTION

async def check_model_drift(niche: str | None = None) -> dict:
    """Check if model performance is drifting by comparing recent predictions
    vs outcomes. Triggers retrain alert if AUC drops below threshold."""
    pool = await get_pool()

    query = """
        SELECT rf.model_predicted, po.is_success
        FROM research_features rf
        JOIN performance_outcomes po ON rf.content_id = po.content_id
        WHERE rf.model_predicted IS NOT NULL
          AND po.is_success IS NOT NULL
          AND rf.created_at > NOW() - INTERVAL '14 days'
    """
    params = []
    if niche:
        query += " AND rf.channel_id IN (SELECT channel_id FROM channels WHERE niche = $1)"
        params.append(niche)

    rows = await pool.fetch(query, *params)

    if len(rows) < 10:
        return {"status": "insufficient_data", "samples": len(rows)}

    predictions = [float(r["model_predicted"]) for r in rows]
    actuals = [1 if r["is_success"] else 0 for r in rows]

    def _check():
        from sklearn.metrics import roc_auc_score
        try:
            auc = roc_auc_score(actuals, predictions)
            return float(auc)
        except ValueError:
            return 0.5

    recent_auc = await asyncio.to_thread(_check)

    needs_retrain = recent_auc < 0.55  # Threshold for retraining

    result = {
        "recent_auc": round(recent_auc, 4),
        "samples": len(rows),
        "needs_retrain": needs_retrain,
        "threshold": 0.55,
    }

    if needs_retrain:
        logger.warning("drift.detected", niche=niche, auc=round(recent_auc, 3))
    else:
        logger.info("drift.ok", niche=niche, auc=round(recent_auc, 3))

    return result
