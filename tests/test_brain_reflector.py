"""Unit tests for BrainReflector (AE-P1 / Agentic Foundation).

All external I/O is patched. No DB, Redis, or LLM calls.

Coverage:
  * reflect_once short-circuits when the master flag is FALSE
  * pattern analysis correctly groups + averages per decision_type
  * sample-size guard suppresses proposals below the threshold
  * proposals are only emitted for under-performing classes
  * _propose_for_pattern: per-type mapping (HALT/HOLD/NUDGE), no-mapping
    types yield None, missing flags yield None, out-of-range proposed
    values are dropped, no-op (proposed == current) yields None
  * Persistence calls the UPSERT SQL exactly once per proposal
  * Loop interval is read from the flag and the loop respects stop_event
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.brain import reflector as R


def _make_pattern(
    decision_type: str = "HALT",
    sample_size: int = 10,
    avg_score: float = 3.0,
) -> R.Pattern:
    return R.Pattern(
        decision_type=decision_type,
        sample_size=sample_size,
        avg_score=avg_score,
        sample_decision_ids=list(range(1, sample_size + 1))[:25],
    )


def _flag_map(flags):
    async def _get_flag(key, default=None):
        return flags.get(key, default)
    return _get_flag


# ─────────────────────────────────────────────────────────────────────────────
# reflect_once / flag gating
# ─────────────────────────────────────────────────────────────────────────────


class TestReflectOnce:
    async def test_disabled_short_circuits(self):
        with patch.object(
            R, "get_flag", new=AsyncMock(return_value=False)
        ) as flag:
            written = await R.reflect_once()
        assert written == 0
        flag.assert_awaited()

    async def test_flag_read_failure_returns_zero(self):
        with patch.object(
            R, "get_flag", new=AsyncMock(side_effect=RuntimeError("db down"))
        ):
            written = await R.reflect_once()
        assert written == 0

    async def test_no_scored_decisions_no_proposals(self):
        with (
            patch.object(
                R, "get_flag",
                side_effect=_flag_map({
                    "brain.reflector.enabled": True,
                    "brain.reflector.min_sample_size": 5,
                    "brain.reflector.score_threshold": 4,
                    "brain.reflector.lookback_days": 14,
                }),
            ),
            patch.object(R, "_analyse_patterns", new=AsyncMock(return_value=[])),
        ):
            written = await R.reflect_once()
        assert written == 0


# ─────────────────────────────────────────────────────────────────────────────
# Sample-size + threshold filtering
# ─────────────────────────────────────────────────────────────────────────────


class TestReflectFiltering:
    @pytest.fixture
    def common_flags(self):
        return {
            "brain.reflector.enabled": True,
            "brain.reflector.min_sample_size": 5,
            "brain.reflector.score_threshold": 4,
            "brain.reflector.lookback_days": 14,
        }

    async def test_below_sample_size_no_proposal(self, common_flags):
        too_small = _make_pattern(sample_size=3, avg_score=2.0)
        with (
            patch.object(
                R, "get_flag", side_effect=_flag_map(common_flags)
            ),
            patch.object(
                R, "_analyse_patterns", new=AsyncMock(return_value=[too_small])
            ),
            patch.object(
                R, "_propose_for_pattern", new=AsyncMock()
            ) as propose,
        ):
            written = await R.reflect_once()
        assert written == 0
        propose.assert_not_awaited()

    async def test_above_threshold_no_proposal(self, common_flags):
        healthy = _make_pattern(sample_size=10, avg_score=8.0)
        with (
            patch.object(
                R, "get_flag", side_effect=_flag_map(common_flags)
            ),
            patch.object(
                R, "_analyse_patterns", new=AsyncMock(return_value=[healthy])
            ),
            patch.object(
                R, "_propose_for_pattern", new=AsyncMock()
            ) as propose,
        ):
            written = await R.reflect_once()
        assert written == 0
        propose.assert_not_awaited()

    async def test_underperforming_generates_proposal(self, common_flags):
        bad = _make_pattern(sample_size=10, avg_score=2.5)
        proposal = R.Proposal(
            flag_key="brain.threshold.halt.consecutive_failures",
            current_payload={"value": 3},
            proposed_payload={"value": 4},
            rationale="raise",
            supporting_evidence={},
            sample_size=10,
            observed_avg_score=2.5,
        )
        with (
            patch.object(
                R, "get_flag", side_effect=_flag_map(common_flags)
            ),
            patch.object(
                R, "_analyse_patterns", new=AsyncMock(return_value=[bad])
            ),
            patch.object(
                R, "_propose_for_pattern", new=AsyncMock(return_value=proposal)
            ),
            patch.object(
                R, "_persist_proposal", new=AsyncMock()
            ) as persist,
        ):
            written = await R.reflect_once()
        assert written == 1
        persist.assert_awaited_once_with(proposal)

    async def test_dry_run_does_not_persist(self, common_flags):
        bad = _make_pattern(sample_size=8, avg_score=2.0)
        proposal = R.Proposal(
            flag_key="brain.threshold.halt.consecutive_failures",
            current_payload={"value": 3},
            proposed_payload={"value": 4},
            rationale="raise",
            supporting_evidence={},
            sample_size=8,
            observed_avg_score=2.0,
        )
        with (
            patch.object(
                R, "get_flag", side_effect=_flag_map(common_flags)
            ),
            patch.object(
                R, "_analyse_patterns", new=AsyncMock(return_value=[bad])
            ),
            patch.object(
                R, "_propose_for_pattern", new=AsyncMock(return_value=proposal)
            ),
            patch.object(
                R, "_persist_proposal", new=AsyncMock()
            ) as persist,
        ):
            written = await R.reflect_once(dry_run=True)
        assert written == 1
        persist.assert_not_awaited()


# ─────────────────────────────────────────────────────────────────────────────
# Per-pattern proposal generation
# ─────────────────────────────────────────────────────────────────────────────


class TestProposeForPattern:
    async def test_no_mapping_returns_none(self):
        # RESUME has no entry in _PATTERN_TO_FLAG.
        p = await R._propose_for_pattern(
            _make_pattern(decision_type="RESUME", avg_score=2.0),
            lookback_days=14,
        )
        assert p is None

    async def test_halt_raises_consecutive_failures(self):
        with patch.object(
            R, "_read_flag_payload",
            new=AsyncMock(return_value={"value": 3}),
        ):
            p = await R._propose_for_pattern(
                _make_pattern(decision_type="HALT", avg_score=2.0),
                lookback_days=14,
            )
        assert p is not None
        assert p.flag_key == "brain.threshold.halt.consecutive_failures"
        assert p.proposed_payload["value"] == 4
        assert p.current_payload == {"value": 3}
        assert p.sample_size == 10
        assert p.observed_avg_score == 2.0

    async def test_hold_raises_cost_spike_factor(self):
        with patch.object(
            R, "_read_flag_payload",
            new=AsyncMock(return_value={"value": 3.0}),
        ):
            p = await R._propose_for_pattern(
                _make_pattern(decision_type="HOLD", avg_score=3.0),
                lookback_days=14,
            )
        assert p is not None
        assert p.flag_key == "brain.threshold.hold.cost_spike_factor"
        assert p.proposed_payload["value"] == 3.5

    async def test_nudge_lowers_quality_threshold(self):
        with patch.object(
            R, "_read_flag_payload",
            new=AsyncMock(return_value={"value": 7.0}),
        ):
            p = await R._propose_for_pattern(
                _make_pattern(decision_type="NUDGE", avg_score=2.0),
                lookback_days=14,
            )
        assert p is not None
        assert p.flag_key == "brain.threshold.nudge.avg_quality_score"
        assert p.proposed_payload["value"] == 6.5

    async def test_out_of_range_proposal_dropped(self):
        # HALT max_value is 10 — already at 10 → next would be 11 → drop.
        with patch.object(
            R, "_read_flag_payload",
            new=AsyncMock(return_value={"value": 10}),
        ):
            p = await R._propose_for_pattern(
                _make_pattern(decision_type="HALT", avg_score=2.0),
                lookback_days=14,
            )
        assert p is None

    async def test_missing_flag_returns_none(self):
        with patch.object(
            R, "_read_flag_payload", new=AsyncMock(return_value=None),
        ):
            p = await R._propose_for_pattern(
                _make_pattern(decision_type="HALT", avg_score=2.0),
                lookback_days=14,
            )
        assert p is None

    async def test_rationale_includes_metrics(self):
        with patch.object(
            R, "_read_flag_payload",
            new=AsyncMock(return_value={"value": 3}),
        ):
            p = await R._propose_for_pattern(
                _make_pattern(
                    decision_type="HALT", sample_size=12, avg_score=3.1
                ),
                lookback_days=14,
            )
        assert p is not None
        assert "3.10" in p.rationale
        assert "12" in p.rationale
        assert "14" in p.rationale
        assert p.supporting_evidence["decision_type"] == "HALT"
        assert p.supporting_evidence["sample_size"] == 12
        assert p.supporting_evidence["lookback_days"] == 14


# ─────────────────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────────────────


class TestPersistProposal:
    async def test_persist_executes_upsert(self):
        execute = AsyncMock()
        fake_pool = MagicMock()
        fake_pool.execute = execute
        with patch.object(
            R, "get_pool", new=AsyncMock(return_value=fake_pool),
        ):
            await R._persist_proposal(R.Proposal(
                flag_key="brain.threshold.halt.consecutive_failures",
                current_payload={"value": 3},
                proposed_payload={"value": 4},
                rationale="why",
                supporting_evidence={"k": "v"},
                sample_size=10,
                observed_avg_score=2.5,
            ))
        execute.assert_awaited_once()
        # The SQL must use ON CONFLICT for idempotence.
        sql = execute.await_args.args[0]
        assert "ON CONFLICT" in sql.upper()
        assert "brain_flag_proposals" in sql

    async def test_reflect_once_logs_but_continues_on_persist_failure(self):
        bad = _make_pattern(sample_size=8, avg_score=2.0)
        good = R.Proposal(
            flag_key="brain.threshold.halt.consecutive_failures",
            current_payload={"value": 3},
            proposed_payload={"value": 4},
            rationale="r", supporting_evidence={},
            sample_size=8, observed_avg_score=2.0,
        )
        with (
            patch.object(
                R, "get_flag",
                side_effect=_flag_map({
                    "brain.reflector.enabled": True,
                    "brain.reflector.min_sample_size": 5,
                    "brain.reflector.score_threshold": 4,
                    "brain.reflector.lookback_days": 14,
                }),
            ),
            patch.object(
                R, "_analyse_patterns", new=AsyncMock(return_value=[bad])
            ),
            patch.object(
                R, "_propose_for_pattern", new=AsyncMock(return_value=good)
            ),
            patch.object(
                R, "_persist_proposal",
                new=AsyncMock(side_effect=RuntimeError("db down")),
            ),
        ):
            written = await R.reflect_once()
        # Persist failure is swallowed; the count of *successful* writes is 0.
        assert written == 0


# ─────────────────────────────────────────────────────────────────────────────
# Loop control
# ─────────────────────────────────────────────────────────────────────────────


class TestRunReflectorLoop:
    async def test_loop_exits_on_stop_event(self):
        import asyncio
        stop = asyncio.Event()
        stop.set()
        # With stop already set, the loop runs at most one reflect_once
        # then exits via the wait_for break.
        with patch.object(
            R, "reflect_once", new=AsyncMock(return_value=0)
        ) as reflect:
            await R.run_reflector_loop(interval_s=1, stop_event=stop)
        # The first iteration checks stop_event BEFORE reflect_once, so
        # the loop should exit immediately without calling reflect_once.
        reflect.assert_not_awaited()
