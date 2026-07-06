#!/usr/bin/env python3
"""Compression savings dashboard — like ``sqz gain`` for Autoniix.

Usage::

    python scripts/compression_stats.py              # Last 7 days summary
    python scripts/compression_stats.py --days 30    # Last 30 days
    python scripts/compression_stats.py --breakdown  # Per-engine + daily
    python scripts/compression_stats.py --watch      # Live refresh every 5s

Reads from ``~/.autoniix/compression_stats.db`` (written by the
compressor middleware in ``src/llm/compressor.py``).

Part of AE-520 / Cost Optimization.
"""
from __future__ import annotations

import argparse
import os
import sys
import time


def _bar(value: int, max_val: int, width: int = 40) -> str:
    """Simple ASCII bar chart."""
    if max_val == 0:
        return ""
    filled = int(value / max_val * width)
    return "█" * filled + "░" * (width - filled)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compression savings dashboard for Autoniix",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to report (default: 7)",
    )
    parser.add_argument(
        "--breakdown", action="store_true",
        help="Show per-engine and daily breakdown",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Live refresh every 5 seconds",
    )
    args = parser.parse_args()

    # Ensure the src package is importable.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from llm.compressor import get_savings_report

    def print_report() -> None:
        report = get_savings_report(days=args.days, breakdown=args.breakdown)

        if "error" in report:
            print(f"Error: {report['error']}")
            return

        total = report["total_compressions"]
        if total == 0:
            print(f"No compression data for the last {args.days} days.")
            print("Set LLM_COMPRESSION=fast or LLM_COMPRESSION=max to start tracking.")
            return

        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║           Autoniix — Token Compression Report               ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print(f"║  Period: last {args.days} days")
        print(f"║  Compressions: {total:,}")
        print(f"║  Tokens in:    {report['total_tokens_in']:,}")
        print(f"║  Tokens out:   {report['total_tokens_out']:,}")
        print(f"║  Tokens saved: {report['total_tokens_saved']:,}")
        print(f"║  Avg reduction: {report['avg_reduction_pct']}%")
        print("╚══════════════════════════════════════════════════════════════╝")

        if args.breakdown:
            engines = report.get("by_engine", [])
            if engines:
                print()
                print("── Per-Engine Breakdown ──")
                max_saved = max(e["saved"] for e in engines) if engines else 1
                for e in engines:
                    bar = _bar(e["saved"], max_saved)
                    print(
                        f"  {e['engine']:<20} {e['count']:>6,} passes  "
                        f"saved: {e['saved']:>10,} tokens  {bar}"
                    )

            daily = report.get("daily", [])
            if daily:
                print()
                print("── Daily Breakdown ──")
                max_saved = max(d["saved"] for d in daily) if daily else 1
                for d in daily:
                    bar = _bar(d["saved"], max_saved)
                    print(
                        f"  {d['day']}  {d['count']:>5,} passes  "
                        f"saved: {d['saved']:>10,} tokens  {bar}"
                    )
        print()

    if args.watch:
        try:
            while True:
                os.system("clear" if os.name != "nt" else "cls")
                print_report()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nExiting.")
    else:
        print_report()


if __name__ == "__main__":
    main()
