"""Unit tests for AE-511 / P0 — Brain directive activity + workflow signal.

We test the activity and the workflow's `_check_brain_directive` helper in
isolation. The Temporal-runtime-only parts (signal dispatch, full workflow
execution) are covered by integration tests in `tests/e2e/`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from temporal_workers.activities.brain import brain_directive_check_activity


@pytest.mark.asyncio
async def test_activity_short_circuits_when_advisory_mode_is_on(mock_pool):
    """Default behaviour: advisory_mode=TRUE → no DB read, return {}."""
    with patch(
        "temporal_workers.activities.brain.get_flag",
        AsyncMock(return_value=True),
    ):
        result = await brain_directive_check_activity("CH_test", "VID_x")
    assert result == {}
    mock_pool.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_activity_returns_empty_when_no_decision_exists(mock_pool):
    """No rows for any scope → return {} so workflow proceeds unchanged."""
    mock_pool.fetchrow.return_value = None
    with patch(
        "temporal_workers.activities.brain.get_flag",
        AsyncMock(return_value=False),
    ):
        result = await brain_directive_check_activity("CH_test", "VID_x")
    assert result == {}


@pytest.mark.asyncio
async def test_activity_returns_halt_when_unresolved_halt_row_exists(mock_pool):
    mock_pool.fetchrow.return_value = {
        "id": 7,
        "decision_type": "HALT",
        "scope": "channel",
        "scope_id": "CH_test",
        "directive": {"reason_code": "copyright"},
        "reasoning": "owned-music match in scene 3",
        "confidence": 0.95,
    }
    with patch(
        "temporal_workers.activities.brain.get_flag",
        AsyncMock(return_value=False),
    ):
        result = await brain_directive_check_activity("CH_test", None)
    assert result["action"] == "HALT"
    assert result["halting"] is True
    assert result["decision_id"] == 7
    assert result["reasoning"] == "owned-music match in scene 3"


@pytest.mark.asyncio
async def test_activity_returns_non_halting_for_advise_decision(mock_pool):
    mock_pool.fetchrow.return_value = {
        "id": 9,
        "decision_type": "ADVISE",
        "scope": "channel",
        "scope_id": "CH_test",
        "directive": {},
        "reasoning": "fyi only",
        "confidence": 0.5,
    }
    with patch(
        "temporal_workers.activities.brain.get_flag",
        AsyncMock(return_value=False),
    ):
        result = await brain_directive_check_activity("CH_test", None)
    assert result["action"] == "ADVISE"
    assert result["halting"] is False


@pytest.mark.asyncio
async def test_activity_never_raises_on_db_error(mock_pool):
    """A DB error must NOT break the workflow."""
    mock_pool.fetchrow.side_effect = RuntimeError("connection refused")
    with patch(
        "temporal_workers.activities.brain.get_flag",
        AsyncMock(return_value=False),
    ):
        result = await brain_directive_check_activity("CH_test", None)
    assert result == {}


def test_check_brain_directive_noop_when_directive_empty():
    from temporal_workers.workflows.video_production import VideoProductionWorkflow

    wf = VideoProductionWorkflow()
    wf._brain_directive = None
    wf._check_brain()
    wf._brain_directive = {}
    wf._check_brain()


def test_check_brain_directive_noop_for_non_halting_actions():
    from temporal_workers.workflows.video_production import VideoProductionWorkflow

    wf = VideoProductionWorkflow()
    wf._brain_directive = {"action": "ADVISE", "reasoning": "fyi"}
    wf._check_brain()


def test_check_brain_directive_raises_application_error_on_halt():
    from temporalio.exceptions import ApplicationError

    from temporal_workers.workflows.video_production import VideoProductionWorkflow

    wf = VideoProductionWorkflow()
    wf._brain_directive = {"action": "HALT", "reasoning": "policy violation"}
    with patch(
        "temporal_workers.workflows.video_production.workflow.logger.warning",
        lambda *a, **k: None,
    ):
        with pytest.raises(ApplicationError) as exc:
            wf._check_brain()
    assert exc.value.non_retryable is True
    assert exc.value.type == "BrainHaltException"


def test_check_brain_directive_raises_retryable_on_hold():
    from temporalio.exceptions import ApplicationError

    from temporal_workers.workflows.video_production import VideoProductionWorkflow

    wf = VideoProductionWorkflow()
    wf._brain_directive = {"action": "HOLD", "reasoning": "wait for legal review"}
    with patch(
        "temporal_workers.workflows.video_production.workflow.logger.warning",
        lambda *a, **k: None,
    ):
        with pytest.raises(ApplicationError) as exc:
            wf._check_brain()
    assert exc.value.non_retryable is False
