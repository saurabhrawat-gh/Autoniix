"""Unit tests for OutcomeScorer (AE-P1 / Agentic Foundation).

All external I/O is patched. No DB, no LLM calls.

Coverage:
  * score_once short-circuits when the master flag is FALSE
  * Per-decision-type scoring functions return the expected
    (score, outcome_jsonb) tuples — and None when there is not
    enough data yet (so the next pass retries).
  * Unknown decision types skip cleanly.
  * Persistence emits the expected UPDATE.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services_api.brain import scorer as S


def _flag_map(flags):
    async def _get_flag(key, default=None):
        return flags.get(key, default)
    return _get_flag


def _row(
    *,
    id_: int = 1,
    decision_type: str = "HALT",
    scope: str = "channel",
    scope_id: str = "ch1",
    resolved_offset_days: int = 10,
):
    now = datetime.now(timezone.utc)
    return {
        "id": id_,
        "decision_type": decision_type,
        "scope": scope,
        "scope_id": scope_id,
        "created_at": now - timedelta(days=resolved_offset_days + 1),
        "resolved_at": now - timedelta(days=resolved_offset_days),
    }




class TestScoreOnce:
    async def test_disabled_short_circuits(self):
        with patch.object(
            S, "get_flag", new=AsyncMock(return_value=False)
        ):
            written = await S.score_once()
        assert written == 0

    async def test_flag_read_failure_returns_zero(self):
        with patch.object(
            S, "get_flag", new=AsyncMock(side_effect=RuntimeError("db"))
        ):
            written = await S.score_once()
        assert written == 0




class TestScoreHALT:
    async def test_no_post_resume_videos_defaults_to_eight(self):
        with patch.object(
            S, "_post_resolve_scores", new=AsyncMock(return_value=[])
        ):
            result = await S._score_halt(
                _row(decision_type="HALT"),
                window_days=7, min_videos=3,
            )
        assert result is not None
        score, outcome = result
        assert score == 8.0
        assert outcome["scoring_method"] == "halt.no_post_resume_videos"

    async def test_insufficient_samples_returns_none(self):
        with patch.object(
            S, "_post_resolve_scores", new=AsyncMock(return_value=[7.0, 8.0])
        ):
            result = await S._score_halt(
                _row(decision_type="HALT"),
                window_days=7, min_videos=3,
            )
        assert result is None

    async def test_low_post_resume_quality_validates_halt(self):
        with patch.object(
            S, "_post_resolve_scores",
            new=AsyncMock(return_value=[2.0, 3.0, 4.0]),
        ):
            result = await S._score_halt(
                _row(decision_type="HALT"),
                window_days=7, min_videos=3,
            )
        assert result is not None
        score, outcome = result
        assert score == 7.0
        assert outcome["scoring_method"] == "halt.inverted_post_resume_quality"
        assert outcome["post_resume_avg_score"] == 3.0
        assert outcome["sample_size"] == 3

    async def test_high_post_resume_quality_means_false_positive(self):
        with patch.object(
            S, "_post_resolve_scores",
            new=AsyncMock(return_value=[9.0, 9.0, 9.0]),
        ):
            result = await S._score_halt(
                _row(decision_type="HALT"),
                window_days=7, min_videos=3,
            )
        assert result is not None
        score, _ = result
        assert score == 1.0

    async def test_missing_scope_id_returns_none(self):
        result = await S._score_halt(
            _row(decision_type="HALT", scope_id=None),
            window_days=7, min_videos=3,
        )
        assert result is None


class TestScoreHOLD:
    async def test_delivered_video_uses_its_score(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={
            "status": "delivered",
            "final_composite_score": 8.4,
        })
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            result = await S._score_hold(
                _row(decision_type="HOLD", scope="video", scope_id="v1"),
                window_days=7,
            )
        assert result is not None
        score, outcome = result
        assert score == 8.4
        assert outcome["scoring_method"] == "hold.delivered_score"

    async def test_failed_video_low_score(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={
            "status": "failed", "final_composite_score": None,
        })
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            result = await S._score_hold(
                _row(decision_type="HOLD", scope="video", scope_id="v1"),
                window_days=7,
            )
        assert result is not None
        score, outcome = result
        assert score == 3.0
        assert outcome["scoring_method"] == "hold.video_failed_after_hold"

    async def test_in_flight_video_defers(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value={
            "status": "in_progress", "final_composite_score": None,
        })
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            result = await S._score_hold(
                _row(decision_type="HOLD", scope="video", scope_id="v1"),
                window_days=7,
            )
        assert result is None

    async def test_missing_video_record_neutral(self):
        pool = MagicMock()
        pool.fetchrow = AsyncMock(return_value=None)
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            result = await S._score_hold(
                _row(decision_type="HOLD", scope="video", scope_id="v_gone"),
                window_days=7,
            )
        assert result is not None
        score, outcome = result
        assert score == 5.0
        assert outcome["scoring_method"] == "hold.video_not_found"


class TestScoreNUDGE:
    async def test_positive_delta_high_score(self):
        pool = MagicMock()
        pool.fetch = AsyncMock(side_effect=[
            [{"final_composite_score": 5.0}, {"final_composite_score": 5.0}],
            [
                {"final_composite_score": 8.0},
                {"final_composite_score": 8.0},
                {"final_composite_score": 8.0},
            ],
        ])
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            result = await S._score_nudge(
                _row(decision_type="NUDGE"),
                window_days=7, min_videos=3,
            )
        assert result is not None
        score, outcome = result
        assert score == 10.0
        assert outcome["delta"] == 3.0

    async def test_negative_delta_low_score(self):
        pool = MagicMock()
        pool.fetch = AsyncMock(side_effect=[
            [{"final_composite_score": 8.0}, {"final_composite_score": 8.0}],
            [
                {"final_composite_score": 5.0},
                {"final_composite_score": 5.0},
                {"final_composite_score": 5.0},
            ],
        ])
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            result = await S._score_nudge(
                _row(decision_type="NUDGE"),
                window_days=7, min_videos=3,
            )
        assert result is not None
        score, _ = result
        assert score == 0.0

    async def test_insufficient_post_samples_defers(self):
        pool = MagicMock()
        pool.fetch = AsyncMock(side_effect=[
            [{"final_composite_score": 5.0}],
            [{"final_composite_score": 6.0}],
        ])
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            result = await S._score_nudge(
                _row(decision_type="NUDGE"),
                window_days=7, min_videos=3,
            )
        assert result is None


class TestScoreRESUME:
    async def test_high_post_quality_validates_resume(self):
        with patch.object(
            S, "_post_resolve_scores",
            new=AsyncMock(return_value=[8.0, 8.0, 8.0]),
        ):
            result = await S._score_resume(
                _row(decision_type="RESUME"),
                window_days=7, min_videos=3,
            )
        assert result is not None
        score, outcome = result
        assert score == 8.0
        assert outcome["scoring_method"] == "resume.post_resume_quality"

    async def test_insufficient_samples_defers(self):
        with patch.object(
            S, "_post_resolve_scores", new=AsyncMock(return_value=[7.0])
        ):
            result = await S._score_resume(
                _row(decision_type="RESUME"),
                window_days=7, min_videos=3,
            )
        assert result is None


class TestScoreADVISE:
    def test_neutral_default(self):
        score, outcome = S._score_advise(_row(decision_type="ADVISE"))
        assert score == 5.0
        assert outcome["scoring_method"] == "advise.neutral_default"


class TestScoreDispatch:
    async def test_unknown_decision_type_returns_none(self):
        result = await S._score_decision(
            _row(decision_type="MYSTERY"),
            window_days=7, min_videos=3,
        )
        assert result is None




class TestPersistScore:
    async def test_update_executed(self):
        pool = MagicMock()
        pool.execute = AsyncMock()
        with patch.object(S, "get_pool", new=AsyncMock(return_value=pool)):
            await S._persist_score(
                decision_id=42, score=7.3,
                outcome={"scoring_method": "halt.test"},
            )
        pool.execute.assert_awaited_once()
        sql = pool.execute.await_args.args[0]
        assert "UPDATE brain_decisions" in sql
        assert "outcome_score" in sql




class TestScorePass:
    async def test_persists_one_score_per_eligible_row(self):
        candidate = _row(id_=10, decision_type="HALT")
        pool = MagicMock()
        pool.fetch = AsyncMock(return_value=[candidate])
        flags = {
            "brain.scorer.enabled": True,
            "brain.scorer.measurement_window_days": 7,
            "brain.scorer.min_videos_for_signal": 3,
            "brain.scorer.batch_size": 200,
        }
        with (
            patch.object(S, "get_flag", side_effect=_flag_map(flags)),
            patch.object(S, "get_pool", new=AsyncMock(return_value=pool)),
            patch.object(
                S, "_score_decision",
                new=AsyncMock(return_value=(7.0, {"scoring_method": "halt.x"})),
            ),
            patch.object(S, "_persist_score", new=AsyncMock()) as persist,
        ):
            written = await S.score_once()
        assert written == 1
        persist.assert_awaited_once()

    async def test_skipped_when_score_decision_returns_none(self):
        candidate = _row(id_=11, decision_type="HOLD", scope="video")
        pool = MagicMock()
        pool.fetch = AsyncMock(return_value=[candidate])
        flags = {
            "brain.scorer.enabled": True,
            "brain.scorer.measurement_window_days": 7,
            "brain.scorer.min_videos_for_signal": 3,
            "brain.scorer.batch_size": 200,
        }
        with (
            patch.object(S, "get_flag", side_effect=_flag_map(flags)),
            patch.object(S, "get_pool", new=AsyncMock(return_value=pool)),
            patch.object(S, "_score_decision", new=AsyncMock(return_value=None)),
            patch.object(S, "_persist_score", new=AsyncMock()) as persist,
        ):
            written = await S.score_once()
        assert written == 0
        persist.assert_not_awaited()

    async def test_dry_run_skips_persistence(self):
        candidate = _row(id_=12, decision_type="HALT")
        pool = MagicMock()
        pool.fetch = AsyncMock(return_value=[candidate])
        flags = {
            "brain.scorer.enabled": True,
            "brain.scorer.measurement_window_days": 7,
            "brain.scorer.min_videos_for_signal": 3,
            "brain.scorer.batch_size": 200,
        }
        with (
            patch.object(S, "get_flag", side_effect=_flag_map(flags)),
            patch.object(S, "get_pool", new=AsyncMock(return_value=pool)),
            patch.object(
                S, "_score_decision",
                new=AsyncMock(return_value=(8.0, {"scoring_method": "halt.x"})),
            ),
            patch.object(S, "_persist_score", new=AsyncMock()) as persist,
        ):
            written = await S.score_once(dry_run=True)
        assert written == 1
        persist.assert_not_awaited()




class TestRunScorerLoop:
    async def test_loop_exits_on_stop_event_set_before_entry(self):
        import asyncio
        stop = asyncio.Event()
        stop.set()
        with patch.object(
            S, "score_once", new=AsyncMock(return_value=0)
        ) as score:
            await S.run_scorer_loop(interval_s=1, stop_event=stop)
        score.assert_not_awaited()
