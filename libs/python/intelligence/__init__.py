"""Intelligence package — niche templates, performance feedback, learning loops.

Exports:

* :func:`list_templates` / :func:`get_template` — niche starter presets.
* :func:`build_performance_context` — close the analytics → prompt loop:
  reads top + worst performers from the DB and formats them as compact
  prompt context for research/script services.
* :func:`evaluate_diversity_floor` / :func:`log_bandit_pick` — Phase 10
  anti-mode-collapse mechanism. Bandits call ``evaluate_diversity_floor``
  before selection; if entropy of recent picks is below threshold the
  bandit is overridden with the least-pulled arm.
"""
from intelligence.diversity_floor import (
    evaluate_diversity_floor,
    log_bandit_pick,
)
from intelligence.niche_templates import get_template, list_templates
from intelligence.performance_feedback import build_performance_context
from intelligence.prediction_calibration import (
    get_calibration_metrics,
    get_sample_weights,
    log_prediction,
    update_prediction_actual,
)
from intelligence.system_health import aggregate_health

__all__ = [
    "list_templates", "get_template", "build_performance_context",
    "evaluate_diversity_floor", "log_bandit_pick",
    "log_prediction", "update_prediction_actual",
    "get_calibration_metrics", "get_sample_weights",
    "aggregate_health",
]
