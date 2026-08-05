"""CLI wrapper around providers.clean_slate.run().

Usage:
    python -m scripts.clean_slate_providers --yes

Equivalent BFF endpoint: POST /api/v2/providers/_admin/clean-slate
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from providers.clean_slate import run


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Wipe ALL provider configuration")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    args = parser.parse_args()

    if not args.yes:
        print("This will DELETE all provider credentials, chains, routes, quotas,")
        print("and sandbox runs. Categories, content_modes, and feature flags are kept.")
        reply = input("Type WIPE to confirm: ").strip()
        if reply != "WIPE":
            print("Aborted.")
            return 1

    print("→ Truncating provider tables...")
    await run(verbose=True)
    print("\n✓ Provider clean slate complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
