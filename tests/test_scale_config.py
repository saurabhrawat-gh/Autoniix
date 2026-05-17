"""Phase 6 — scale-out config & invariants.

Static guards that lock in the env-driven sizing so a future refactor
can't silently re-hardcode the knobs and bottleneck the fleet.

These are not load tests (those live in ``tests/load/`` and require a
running stack). These are millisecond-fast checks that the *wiring* is
correct.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config import settings


ROOT = Path(__file__).resolve().parent.parent
PROD = ROOT / "src" / "workers" / "run_production.py"
SCHED = ROOT / "src" / "workers" / "run_scheduler.py"
DB = ROOT / "src" / "db.py"


# Settings carry the new knobs


def test_settings_expose_temporal_sizing():
    assert isinstance(settings.temporal_production_max_activities, int)
    assert isinstance(settings.temporal_production_max_workflow_tasks, int)
    assert isinstance(settings.temporal_scheduler_max_activities, int)
    # Sanity floors — anything below 1 means the worker would idle forever.
    assert settings.temporal_production_max_activities >= 1
    assert settings.temporal_scheduler_max_activities >= 1


def test_settings_expose_db_sizing():
    assert settings.db_pool_min_size >= 1
    assert settings.db_pool_max_size >= settings.db_pool_min_size
    # Statement timeout must be positive and not absurdly large
    # (>1h would defeat the purpose).
    assert 1_000 <= settings.db_statement_timeout_ms <= 3_600_000


# Workers actually use the settings (not hardcoded)


def test_production_worker_uses_settings_for_concurrency():
    src = PROD.read_text()
    assert "settings.temporal_production_max_activities" in src
    assert "settings.temporal_production_max_workflow_tasks" in src
    # Hardcoded numbers would silently override the env. These specific
    # literals were the previous values — flag if they reappear.
    assert "max_concurrent_activities=5" not in src
    assert "max_concurrent_workflow_tasks=10" not in src


def test_scheduler_worker_uses_settings_for_concurrency():
    src = SCHED.read_text()
    assert "settings.temporal_scheduler_max_activities" in src
    assert "max_concurrent_activities=3" not in src


# DB pool wires statement_timeout through


def test_db_pool_applies_statement_timeout_per_connection():
    src = DB.read_text()
    # The init hook is the safe place — any caller that forgets
    # `SET LOCAL statement_timeout` is still protected.
    assert "_init_connection" in src
    assert "statement_timeout" in src
    assert "init=_init_connection" in src
    # Pool sizing must come from settings (not "min_size=2, max_size=10").
    assert "settings.db_pool_min_size" in src
    assert "settings.db_pool_max_size" in src


def test_pool_stats_helper_is_exported():
    """The fleet-health endpoint depends on this name."""
    from src import db
    assert hasattr(db, "get_pool_stats")
    out = db.get_pool_stats()
    # When the pool isn't initialised the helper still returns a shape
    # the dashboard can consume — never None.
    assert isinstance(out, dict)
    assert {"size", "idle", "min_size", "max_size"} <= out.keys()
