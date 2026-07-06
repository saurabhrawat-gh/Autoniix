"""Idempotent migration runner.

Applies every ``scripts/migrations/*.sql`` file in lexical order, skipping
any whose checksum already matches a row in ``schema_migrations``.

Usage:
    python -m scripts.run_migrations           # apply all pending
    python -m scripts.run_migrations --dry-run # show what would run
    python -m scripts.run_migrations --status  # list applied + pending
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

import asyncpg

from core.config import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
TRACKER_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       VARCHAR(40)   PRIMARY KEY,
    applied_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    checksum      VARCHAR(64)   NOT NULL,
    description   TEXT
);
"""


def _discover() -> list[tuple[str, Path, str]]:
    """Return ``[(version, path, checksum)]`` sorted by version."""
    out: list[tuple[str, Path, str]] = []
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = p.stem.split("_", 1)[0]
        body = p.read_text()
        checksum = hashlib.sha256(body.encode()).hexdigest()
        out.append((version, p, checksum))
    return out


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


async def status() -> None:
    conn = await _connect()
    try:
        await conn.execute(TRACKER_BOOTSTRAP)
        rows = await conn.fetch(
            "SELECT version, applied_at, checksum FROM schema_migrations"
        )
        applied = {r["version"]: r for r in rows}
        for version, path, checksum in _discover():
            row = applied.get(version)
            if not row:
                print(f"  [PENDING] {path.name}")
            elif row["checksum"] != checksum:
                print(f"  [DRIFT  ] {path.name}  (checksum mismatch — file changed since apply)")
            else:
                print(f"  [APPLIED] {path.name}  @ {row['applied_at']:%Y-%m-%d %H:%M:%S}")
    finally:
        await conn.close()


async def apply(dry_run: bool = False) -> int:
    conn = await _connect()
    applied_count = 0
    try:
        await conn.execute(TRACKER_BOOTSTRAP)
        rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
        applied = {r["version"]: r["checksum"] for r in rows}

        for version, path, checksum in _discover():
            if version in applied:
                if applied[version] != checksum:
                    print(
                        f"WARN: {path.name} checksum drift "
                        f"({applied[version][:8]} → {checksum[:8]}). "
                        "Skipping (re-run is unsafe; create a follow-up migration)."
                    )
                continue
            if dry_run:
                print(f"WOULD APPLY: {path.name}")
                continue
            print(f"APPLY: {path.name}")
            body = path.read_text()
            async with conn.transaction():
                await conn.execute(body)
                await conn.execute(
                    "INSERT INTO schema_migrations(version, checksum, description) "
                    "VALUES ($1, $2, $3)",
                    version, checksum, path.stem,
                )
            applied_count += 1

        if applied_count == 0 and not dry_run:
            print("No pending migrations.")
        return applied_count
    finally:
        await conn.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--status", action="store_true")
    args = p.parse_args()

    if args.status:
        asyncio.run(status())
        return 0
    asyncio.run(apply(dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
