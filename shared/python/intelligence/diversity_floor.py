"""Diversity floor (Phase 10).

Self-tuning systems with bandit feedback have a known failure mode:
they converge on a narrow style that performs well, audience fatigue
causes performance to degrade, and the bandit can't escape because
every variant it tries is worse than its recent average. **This is a
property of the algorithm, not a maybe** — Phases 5/7/9 all tighten
the feedback loop, accelerating the day this happens unless we add a
forcing function for novelty.

The mechanism:

1. Every bandit selection is logged to ``bandit_picks``.
2. Before each new selection, look at the last N picks for this
   (channel, bandit_type) and compute the **normalised Shannon entropy**
   of the arm distribution. 1.0 = perfectly diverse, 0.0 = single arm
   picked every time.
3. If entropy < ``DIVERSITY_THRESHOLD`` we override Thompson sampling
   and pick the **least-pulled** arm instead — a hard exploration
   nudge that breaks the convergence pattern.
4. Either way, log the resulting pick (with ``forced_exploration``
   flagged when applicable) so the floor's behaviour is auditable.

The pure-function core (``shannon_entropy`` and
``should_force_exploration``) is testable without a DB. The wrapper
layer reads/writes ``bandit_picks``.
"""
from __future__ import annotations

import math
from typing import Iterable

import structlog

logger = structlog.get_logger()




DEFAULT_LOOKBACK_N = 20

DIVERSITY_THRESHOLD = 0.55

MIN_PICKS_FOR_GUARD = 8




def shannon_entropy(counts: Iterable[int]) -> float:
    """Normalised Shannon entropy of an arm-pick histogram.

    Returns a value in [0, 1] where:

    * 1.0 = perfectly uniform (every arm picked equally)
    * 0.0 = degenerate (single arm picked every time, or no picks)

    Normalisation divides by ``log(k)`` where ``k`` is the number of
    arms with at least one pick. So a bandit with 3 active arms and
    a bandit with 7 active arms both get 1.0 when their picks are
    uniform — entropy is comparable across bandits.
    """
    counts = [c for c in counts if c > 0]
    n_arms = len(counts)
    if n_arms <= 1:
        return 0.0
    total = sum(counts)
    if total <= 0:
        return 0.0
    probabilities = [c / total for c in counts]
    raw_entropy = -sum(p * math.log(p) for p in probabilities)
    max_entropy = math.log(n_arms)
    if max_entropy <= 0:
        return 0.0
    return raw_entropy / max_entropy


def should_force_exploration(
    counts: list[int],
    *,
    threshold: float = DIVERSITY_THRESHOLD,
    min_picks: int = MIN_PICKS_FOR_GUARD,
) -> bool:
    """Decide whether to override Thompson with a least-pulled pick.

    Returns False when:
    * Total recent picks < min_picks (the floor never fires during
      a channel's early-learning phase).
    * Entropy ≥ threshold (population is diverse enough).

    Returns True only when there's clear collapse evidence and enough
    data to trust the call.
    """
    total = sum(counts)
    if total < min_picks:
        return False
    return shannon_entropy(counts) < threshold


def pick_least_pulled(
    arm_counts: dict[str, int],
    *,
    available_arms: list[str] | None = None,
) -> str | None:
    """Pick the arm with the fewest recent pulls.

    ``available_arms`` constrains the choice to arms that are
    currently offered (the bandit may have been given a different
    candidate set than what's in history). Ties are broken
    deterministically by arm name so two adjacent forced-exploration
    calls don't accidentally pick the same arm again.
    """
    arms = available_arms if available_arms is not None else list(arm_counts.keys())
    if not arms:
        return None

    def _key(arm: str) -> tuple[int, str]:
        return (arm_counts.get(arm, 0), arm)

    return min(arms, key=_key)




async def log_bandit_pick(
    *,
    niche: str,
    bandit_type: str,
    channel_id: str | None,
    arm_name: str,
    forced_exploration: bool = False,
) -> None:
    """Append one pick to ``bandit_picks``.

    Failure to log is non-fatal — we'd rather have a bandit pick that
    isn't audited than block the pipeline. A persistent log failure
    will surface via the dashboard when diversity scores stay flat.
    """
    try:
        from core.db import get_pool
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO bandit_picks (niche, bandit_type, channel_id,
                                       arm_name, forced_exploration)
            VALUES ($1, $2, $3, $4, $5)
            """,
            niche, bandit_type, channel_id, arm_name, forced_exploration,
        )
    except Exception as exc:
        logger.warning("diversity.log_pick_failed",
                       niche=niche, bandit_type=bandit_type, error=str(exc))


async def get_recent_arm_counts(
    *,
    channel_id: str | None,
    bandit_type: str,
    lookback_n: int = DEFAULT_LOOKBACK_N,
) -> dict[str, int]:
    """Histogram of last ``lookback_n`` arm picks for one channel × bandit.

    Returns ``{}`` on DB failure or empty history; the caller treats
    that as "not enough data, don't force exploration."

    Channel-scoped: mode collapse is per-channel because each channel's
    audience and content style is independent. Niche-wide bandit state
    is shared, but the *recent picks visible to one channel's audience*
    are what matter for that channel's collapse detection.
    """
    if not channel_id:
        return {}
    try:
        from core.db import get_pool
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT arm_name, COUNT(*)::int AS picks
            FROM (
                SELECT arm_name FROM bandit_picks
                WHERE channel_id = $1 AND bandit_type = $2
                ORDER BY picked_at DESC
                LIMIT $3
            ) recent
            GROUP BY arm_name
            """,
            channel_id, bandit_type, lookback_n,
        )
        return {r["arm_name"]: int(r["picks"]) for r in rows}
    except Exception as exc:
        logger.warning("diversity.fetch_counts_failed",
                       channel_id=channel_id, bandit_type=bandit_type, error=str(exc))
        return {}


async def evaluate_diversity_floor(
    *,
    channel_id: str | None,
    bandit_type: str,
    available_arms: list[str],
    lookback_n: int = DEFAULT_LOOKBACK_N,
) -> dict:
    """One-call API for bandit callers.

    Returns:
        ``{
            "force": bool,
            "forced_arm": str | None,
            "entropy": float,
            "n_recent_picks": int,
            "arm_counts": dict[str, int],
        }``

    The bandit checks ``force``: if True and ``forced_arm`` is set,
    use that as the selection (overriding Thompson). The other fields
    are returned so the caller can log them on the audit row.

    Cold-start safe at every step: missing channel_id, empty history,
    DB error → ``force=False``.
    """
    counts = await get_recent_arm_counts(
        channel_id=channel_id, bandit_type=bandit_type, lookback_n=lookback_n,
    )
    count_list = list(counts.values())
    n_recent = sum(count_list)
    entropy = shannon_entropy(count_list) if count_list else 0.0

    force = should_force_exploration(count_list)
    forced_arm = pick_least_pulled(counts, available_arms=available_arms) if force else None

    return {
        "force":          force,
        "forced_arm":     forced_arm,
        "entropy":        round(entropy, 4),
        "n_recent_picks": n_recent,
        "arm_counts":     counts,
    }
