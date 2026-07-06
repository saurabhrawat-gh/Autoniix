"""Phase 10 — diversity floor / anti-mode-collapse tests.

Locks the entropy math and the force-exploration decision logic. The DB
layer (``log_bandit_pick``, ``get_recent_arm_counts``) is exercised
through integration tests; here we test the pure-function core that
makes the actual safety call.
"""
from __future__ import annotations

import math

import pytest

from intelligence.diversity_floor import (
    DEFAULT_LOOKBACK_N,
    DIVERSITY_THRESHOLD,
    MIN_PICKS_FOR_GUARD,
    pick_least_pulled,
    shannon_entropy,
    should_force_exploration,
)




def test_entropy_is_one_for_uniform_distribution():
    """Perfectly uniform picks across N arms → normalised entropy = 1."""
    for n_arms in [2, 3, 5, 7]:
        counts = [10] * n_arms
        assert shannon_entropy(counts) == pytest.approx(1.0, abs=1e-9)


def test_entropy_is_zero_for_single_arm():
    """All picks on one arm → degenerate → entropy = 0."""
    assert shannon_entropy([20]) == 0.0


def test_entropy_zero_for_empty_or_no_picks():
    assert shannon_entropy([]) == 0.0
    assert shannon_entropy([0, 0, 0]) == 0.0


def test_entropy_drops_as_distribution_skews():
    """Locking the directionality: a more-peaked distribution must
    have *lower* entropy than a more-uniform one."""
    uniform     = shannon_entropy([5, 5, 5, 5])
    mild_skew   = shannon_entropy([8, 4, 4, 4])
    heavy_skew  = shannon_entropy([16, 2, 1, 1])
    near_collapse = shannon_entropy([19, 1])
    assert uniform > mild_skew > heavy_skew > near_collapse


def test_entropy_normalisation_makes_bandits_comparable():
    """Two uniform bandits with different arm counts both score 1.0.
    Without normalisation a 7-arm bandit would dominate a 3-arm bandit
    even at uniform — defeats comparability."""
    e3 = shannon_entropy([5, 5, 5])
    e7 = shannon_entropy([5, 5, 5, 5, 5, 5, 5])
    assert e3 == pytest.approx(e7)


def test_entropy_ignores_zero_arms():
    """Arms with zero picks shouldn't punish entropy as if they were
    'present but unpicked' — they're effectively not in the bandit's
    active set for the purposes of recent-history scoring."""
    e_with_zeros = shannon_entropy([5, 5, 0, 0])
    e_without    = shannon_entropy([5, 5])
    assert e_with_zeros == pytest.approx(e_without)




def test_force_exploration_off_when_below_min_picks():
    """During the channel's early-learning phase the floor must not
    fire — Thompson needs room to converge."""
    counts = [MIN_PICKS_FOR_GUARD - 1]
    assert should_force_exploration(counts) is False


def test_force_exploration_on_when_collapsed_and_enough_data():
    """Heavy collapse (one arm dominating) past min_picks → force."""
    counts = [18, 2]
    assert sum(counts) >= MIN_PICKS_FOR_GUARD
    assert shannon_entropy(counts) < DIVERSITY_THRESHOLD
    assert should_force_exploration(counts) is True


def test_force_exploration_off_when_diverse_population():
    """Healthy diverse picks past min_picks → don't fire."""
    counts = [4, 4, 4, 4, 4]
    assert sum(counts) >= MIN_PICKS_FOR_GUARD
    assert shannon_entropy(counts) >= DIVERSITY_THRESHOLD
    assert should_force_exploration(counts) is False


def test_force_exploration_monotone_around_threshold():
    """Near the threshold, lower entropy must produce *more* firing,
    never less. Locks monotonicity without pinning exact counts — the
    threshold itself can be retuned later without breaking this test.

    Measured entropies (against default threshold = 0.55):
      * [14, 4, 2]  -> 0.73  (well above)
      * [16, 3, 1]  -> 0.56  (just above)
      * [17, 2, 1]  -> 0.47  (just below)
      * [17, 1, 1, 1] -> 0.42 (well below)
    """
    ladders = [
        ([14, 4, 2],     False),
        ([17, 2, 1],     True),
        ([17, 1, 1, 1],  True),
    ]
    for counts, expected_force in ladders:
        assert should_force_exploration(counts) is expected_force, (
            f"counts={counts} entropy={shannon_entropy(counts):.3f} "
            f"expected_force={expected_force}"
        )


def test_force_exploration_respects_custom_threshold():
    """Tunable threshold lets ops tighten/loosen per-niche later.

    [17, 2, 1] has entropy ~0.47:
      * with threshold 0.7 (stricter): 0.47 < 0.7 → force
      * with threshold 0.4 (looser):   0.47 > 0.4 → don't force
    """
    counts = [17, 2, 1]
    assert should_force_exploration(counts, threshold=0.7) is True
    assert should_force_exploration(counts, threshold=0.4) is False




def test_pick_least_pulled_returns_minimum_count_arm():
    counts = {"a": 10, "b": 3, "c": 7}
    assert pick_least_pulled(counts) == "b"


def test_pick_least_pulled_prefers_unseen_arms():
    """An arm not in the recent-history dict has count=0 → least pulled.
    This is critical: when a new arm is introduced it should be the
    first thing forced exploration tries."""
    counts = {"a": 10, "b": 3}
    available = ["a", "b", "c_new"]
    assert pick_least_pulled(counts, available_arms=available) == "c_new"


def test_pick_least_pulled_is_deterministic_on_ties():
    """Two arms tied at min pulls → pick the lexicographically first.
    Locking determinism so that two adjacent forced-exploration calls
    don't accidentally produce different picks given identical state."""
    counts = {"alpha": 5, "beta": 5, "gamma": 10}
    assert pick_least_pulled(counts) == "alpha"


def test_pick_least_pulled_handles_empty_available_list():
    assert pick_least_pulled({"a": 1}, available_arms=[]) is None


def test_pick_least_pulled_constrains_to_available():
    """Even if arm 'a' has the lowest count, if it's not in the
    currently-offered arms list, we don't pick it."""
    counts = {"a": 1, "b": 5, "c": 8}
    available = ["b", "c"]
    assert pick_least_pulled(counts, available_arms=available) == "b"




def test_realistic_collapse_scenario():
    """Channel has 20 recent topic picks, 17 on 'fitness_tips' and 3
    spread across other arms. This is exactly the collapse the floor
    is built to catch."""
    counts = [17, 1, 1, 1]
    assert sum(counts) == 20
    assert sum(counts) >= MIN_PICKS_FOR_GUARD
    assert shannon_entropy(counts) < DIVERSITY_THRESHOLD
    assert should_force_exploration(counts) is True


def test_realistic_healthy_scenario():
    """A bandit converging healthily: one arm slightly preferred but
    not dominant. The floor must not fire here."""
    counts = [7, 5, 4, 4]
    assert sum(counts) == 20
    assert shannon_entropy(counts) >= DIVERSITY_THRESHOLD
    assert should_force_exploration(counts) is False


def test_realistic_early_channel_scenario():
    """A channel that's only had 5 picks total: even if collapsed,
    don't intervene — Thompson needs to learn first."""
    counts = [5]
    assert should_force_exploration(counts) is False




def test_constants_have_sensible_values():
    assert 0.0 < DIVERSITY_THRESHOLD < 1.0
    assert MIN_PICKS_FOR_GUARD >= 5
    assert DEFAULT_LOOKBACK_N >= MIN_PICKS_FOR_GUARD


def test_thompson_sample_signatures_accept_channel_id():
    """Both bandit functions must accept channel_id as a kwarg without
    raising. We can't actually call them without a DB but we can verify
    the signature is correct via inspect.

    This catches the regression where Phase 10 wires channel_id but
    one of the two thompson_sample functions is missed."""
    import inspect

    from services_api.research.self_learning import (
        thompson_sample as research_ts,
    )
    from services_api.script.self_learning import (
        thompson_sample as script_ts,
    )

    research_sig = inspect.signature(research_ts)
    script_sig = inspect.signature(script_ts)
    assert "channel_id" in research_sig.parameters
    assert "channel_id" in script_sig.parameters
    assert research_sig.parameters["channel_id"].kind == inspect.Parameter.KEYWORD_ONLY
    assert script_sig.parameters["channel_id"].kind == inspect.Parameter.KEYWORD_ONLY
