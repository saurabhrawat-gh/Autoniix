"""Regression for AE-368 — review /decide endpoint validation.

The original bug: the UI sent action verbs ('approve' / 'reject') but the
backend only accepts state values ('approved' / 'rejected'). Every quick
approve returned 400, but the UI showed success.

This test pins:
* Every valid state value is accepted (no false 400).
* The deprecated verb form ('approve'/'reject') is explicitly rejected
  with a CLEAR error message that names the valid alternatives — so any
  future client repeating the same mistake fails loudly.
* Empty/garbage values are rejected.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from services_api.dashboard.v2.review import DecisionIn, decide


def _principal():
    p = MagicMock()
    p.user_id = 1
    return p


def _request():
    """Fake fastapi.Request — only ``audit`` reads from it."""
    r = MagicMock()
    r.client.host = "127.0.0.1"
    r.headers = {}
    return r


def _patch_pool_with_open_session():
    """Helper context yielding a fake pool that simulates an open session."""
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.execute = AsyncMock(return_value="UPDATE 1")

    class _Conn:
        def __init__(self):
            self.execute = AsyncMock()
            self.fetchrow = AsyncMock(return_value={"id": 1})

        def transaction(self):
            class _T:
                async def __aenter__(_): return _
                async def __aexit__(_, *_a): return False
            return _T()

    class _Acquire:
        def __init__(self, conn): self._conn = conn
        async def __aenter__(self): return self._conn
        async def __aexit__(self, *_a): return False

    conn = _Conn()
    pool.acquire = lambda: _Acquire(conn)
    return pool


@pytest.mark.parametrize("value", ["approved", "needs_edits", "rejected", "regenerating"])
@pytest.mark.asyncio
async def test_every_valid_decision_value_is_accepted(value):
    pool = _patch_pool_with_open_session()
    body = DecisionIn(decision=value)
    with patch("services_api.dashboard.v2.review.get_pool", AsyncMock(return_value=pool)), \
         patch("services_api.dashboard.v2.review.audit", AsyncMock()):
        try:
            await decide("VID_x", body, _request(), _principal())
        except HTTPException as exc:
            assert exc.status_code != 400, (
                f"valid decision={value!r} was rejected: {exc.detail}"
            )


@pytest.mark.parametrize("bad", ["approve", "reject", "approve_video", "yes", "", "APPROVED"])
@pytest.mark.asyncio
async def test_invalid_decision_returns_400_with_clear_message(bad):
    body = DecisionIn(decision=bad)
    with patch("services_api.dashboard.v2.review.get_pool", AsyncMock()), \
         patch("services_api.dashboard.v2.review.audit", AsyncMock()):
        with pytest.raises(HTTPException) as exc:
            await decide("VID_x", body, _request(), _principal())
        assert exc.value.status_code == 400
        assert "approved" in exc.value.detail
        assert "rejected" in exc.value.detail
