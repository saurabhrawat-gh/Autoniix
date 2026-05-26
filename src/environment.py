"""Environment mode stubs — test/prod mode removed.

All functions return production values. This module exists only for
import compatibility with code not yet cleaned up.
"""
from __future__ import annotations


class EnvironmentModeError(RuntimeError):
    """Kept for import compatibility. No longer raised."""
    pass


def set_db_mode_override(mode: str) -> None:  # no-op
    pass


def clear_db_mode_override() -> None:  # no-op
    pass


async def get_mode_from_db() -> str:
    return "production"


def get_mode() -> str:
    return "production"


def is_test() -> bool:
    return False


def is_production() -> bool:
    return True


def require_production(action_name: str) -> None:  # always passes
    pass


def get_storage_prefix() -> str:
    return "prod"


def get_content_id_prefix() -> str:
    return "VID"
