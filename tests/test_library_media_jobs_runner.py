"""Unit tests for the media_jobs runner — AE-355 / Library Sprint."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workers.media_jobs import runner
from src.workers.media_jobs.handlers import resolve as resolve_handler
from src.workers.media_jobs.handlers import skip_handler


@pytest.mark.asyncio
async def test_resolve_returns_skip_handler_for_unknown_kind():
    h = resolve_handler("nonexistent_kind")
    assert h is skip_handler.run


@pytest.mark.asyncio
async def test_resolve_returns_real_handler_for_known_kinds():
    from src.workers.media_jobs.handlers import autotag, embed, probe

    assert resolve_handler("probe") is probe.run
    assert resolve_handler("embed") is embed.run
    assert resolve_handler("autotag") is autotag.run


def _build_pool_with_claim(claim_row: dict | None, asset_row: dict | None):
    """Build a fake pool that returns ``claim_row`` for the SELECT then succeeds on UPDATE."""
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    pool.fetchrow = AsyncMock(return_value=asset_row)

    class _Conn:
        def __init__(self):
            self.execute = AsyncMock()
            self.fetchrow = AsyncMock(return_value=claim_row)
            self.transaction_calls = 0

        def transaction(self):
            class _T:
                async def __aenter__(_self):
                    return _self
                async def __aexit__(_self, *a):
                    return False
            return _T()

    class _Acquire:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *a):
            return False

    conn = _Conn()
    pool.acquire = lambda: _Acquire(conn)
    return pool, conn


@pytest.mark.asyncio
async def test_process_one_returns_false_when_queue_empty():
    pool, _ = _build_pool_with_claim(claim_row=None, asset_row=None)
    assert await runner.process_one(pool) is False


@pytest.mark.asyncio
async def test_process_one_skips_when_asset_was_deleted():
    pool, _conn = _build_pool_with_claim(
        claim_row={
            "id": 1, "asset_id": 99, "kind": "probe",
            "attempts": 0, "max_attempts": 3, "priority": 5,
        },
        asset_row=None,
    )
    assert await runner.process_one(pool) is True
    update_sqls = [c.args[0] for c in pool.execute.await_args_list]
    assert any("status = 'skipped'" in s for s in update_sqls)


@pytest.mark.asyncio
async def test_process_one_dispatches_to_handler_and_marks_done():
    pool, _conn = _build_pool_with_claim(
        claim_row={
            "id": 2, "asset_id": 7, "kind": "probe",
            "attempts": 0, "max_attempts": 3, "priority": 5,
        },
        asset_row={
            "id": 7, "scope": "workspace", "scope_id": None,
            "kind": "image", "display_name": "x.png",
            "storage_key": "dam/wkspc/none/image/abc_x.png",
            "tags": [], "ai_tags": {}, "metadata": {},
            "mime_type": "image/png", "bytes": 1,
            "content_hash": None, "thumbnail_key": None,
        },
    )

    async def fake_handler(_pool, _asset, _job):
        return {"status": "done", "result": {"ok": True}}

    with patch(
        "src.workers.media_jobs.runner.resolve_handler",
        return_value=fake_handler,
    ):
        ran = await runner.process_one(pool)
    assert ran is True
    sqls = [c.args[0] for c in pool.execute.await_args_list]
    assert any("status = 'done'" in s for s in sqls)


@pytest.mark.asyncio
async def test_process_one_reschedules_on_failure_when_attempts_left():
    pool, _conn = _build_pool_with_claim(
        claim_row={
            "id": 3, "asset_id": 7, "kind": "probe",
            "attempts": 0, "max_attempts": 3, "priority": 5,
        },
        asset_row={
            "id": 7, "scope": "workspace", "scope_id": None,
            "kind": "image", "display_name": "x.png",
            "storage_key": "k", "tags": [], "ai_tags": {}, "metadata": {},
            "mime_type": "image/png", "bytes": 1,
            "content_hash": None, "thumbnail_key": None,
        },
    )

    async def fake_handler(_pool, _asset, _job):
        return {"status": "failed", "reason": "transient"}

    with patch(
        "src.workers.media_jobs.runner.resolve_handler",
        return_value=fake_handler,
    ):
        await runner.process_one(pool)

    sqls = [c.args[0] for c in pool.execute.await_args_list]
    assert any("status = 'pending'" in s and "scheduled_at" in s for s in sqls)


@pytest.mark.asyncio
async def test_process_one_marks_failed_when_attempts_exhausted():
    pool, _conn = _build_pool_with_claim(
        claim_row={
            "id": 4, "asset_id": 7, "kind": "probe",
            "attempts": 2, "max_attempts": 3, "priority": 5,
        },
        asset_row={
            "id": 7, "scope": "workspace", "scope_id": None,
            "kind": "image", "display_name": "x.png",
            "storage_key": "k", "tags": [], "ai_tags": {}, "metadata": {},
            "mime_type": "image/png", "bytes": 1,
            "content_hash": None, "thumbnail_key": None,
        },
    )

    async def fake_handler(_pool, _asset, _job):
        return {"status": "failed", "reason": "permanent"}

    with patch(
        "src.workers.media_jobs.runner.resolve_handler",
        return_value=fake_handler,
    ):
        await runner.process_one(pool)

    sqls = [c.args[0] for c in pool.execute.await_args_list]
    assert any("status = 'failed'" in s for s in sqls)


@pytest.mark.asyncio
async def test_unhandled_exception_in_handler_is_recovered():
    pool, _conn = _build_pool_with_claim(
        claim_row={
            "id": 5, "asset_id": 7, "kind": "probe",
            "attempts": 0, "max_attempts": 3, "priority": 5,
        },
        asset_row={
            "id": 7, "scope": "workspace", "scope_id": None,
            "kind": "image", "display_name": "x.png",
            "storage_key": "k", "tags": [], "ai_tags": {}, "metadata": {},
            "mime_type": "image/png", "bytes": 1,
            "content_hash": None, "thumbnail_key": None,
        },
    )

    async def fake_handler(_pool, _asset, _job):
        raise RuntimeError("kaboom")

    with patch(
        "src.workers.media_jobs.runner.resolve_handler",
        return_value=fake_handler,
    ):
        ran = await runner.process_one(pool)
    assert ran is True
    sqls = [c.args[0] for c in pool.execute.await_args_list]
    assert any("status = 'pending'" in s for s in sqls)
