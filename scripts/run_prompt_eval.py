"""Run every JSON case under ``tests/prompt_eval/cases/`` through the
LLM router and emit a pass/fail summary. Exits non-zero on any failure
so CI can gate merges.

Usage::

    python scripts/run_prompt_eval.py
    python scripts/run_prompt_eval.py --case-dir tests/prompt_eval/cases --channel-id EVAL

In test mode (default in CI) the router resolves to ``mock_llm`` so the
suite costs $0 and is fully deterministic. In production it can be
pointed at real providers to track real-model regression.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from quality.prompt_eval import EvalCase, Spec, run_suite  # noqa: E402

from providers.boot import boot_providers  # noqa: E402


def _load_cases(case_dir: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for p in sorted(case_dir.glob("*.json")):
        raw = json.loads(p.read_text())
        spec = Spec(**raw["spec"])
        cases.append(
            EvalCase(
                id=raw["id"],
                category=raw["category"],
                messages=raw["messages"],
                spec=spec,
                temperature=raw.get("temperature", 0.3),
                max_tokens=raw.get("max_tokens", 800),
                response_format=raw.get("response_format", "text"),
            )
        )
    return cases


_REAL_KEY_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")
_LLM_CATEGORIES = (
    "LLM",
    "LLM.RESEARCH",
    "LLM.SCRIPT",
    "LLM.FACTCHECK",
    "LLM.QC",
    "LLM.VISION",
    "LLM.IDEATION",
    "LLM.HOOK",
    "LLM.DIRECTION",
    "LLM.EMOTION",
)


def _maybe_force_mock_ladder() -> None:
    """Route every eval case through mock_llm when no real LLM keys are set.

    The router resolves ladder env vars at call time, so setting them here
    (before boot_providers) guarantees CI never hits a real provider.
    """
    if any(os.getenv(k) for k in _REAL_KEY_ENVS):
        return
    for cat in _LLM_CATEGORIES:
        env_key = "LLM_" + cat.replace(".", "_") + "_LADDER"
        os.environ.setdefault(env_key, "mock_llm")


async def _amain(case_dir: Path, channel_id: str) -> int:
    _maybe_force_mock_ladder()
    boot_providers()
    cases = _load_cases(case_dir)
    if not cases:
        print(f"[prompt-eval] no cases found under {case_dir}")
        return 0
    summary = await run_suite(cases, channel_id=channel_id)
    print(
        json.dumps(
            {
                "total": summary["total"],
                "passed": summary["passed"],
                "failed": summary["failed"],
                "total_cost_usd": summary["total_cost_usd"],
            },
            indent=2,
        )
    )
    for r in summary["results"]:
        marker = "PASS" if r["passed"] else "FAIL"
        print(f"  [{marker}] {r['case_id']}  ({r['provider']}/{r['model']}, ${r['cost_usd']:.4f})")
        if not r["passed"]:
            for f in r["failures"]:
                print(f"      - {f}")
    return 0 if summary["failed"] == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", default="tests/prompt_eval/cases")
    ap.add_argument("--channel-id", default="EVAL")
    args = ap.parse_args()
    rc = asyncio.run(_amain(ROOT / args.case_dir, args.channel_id))
    sys.exit(rc)


if __name__ == "__main__":
    main()
