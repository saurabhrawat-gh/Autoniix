"""Prompt-evaluation scaffold (Phase 4).

A *golden test* for prompts: pin the input, run the prompt through the
configured LLM, score the output against a deterministic spec. The
scaffold is deliberately tiny — five public bits:

* :class:`Spec`         — the assertion bundle for one example
* :class:`EvalCase`     — input + spec
* :class:`EvalResult`   — pass/fail + per-spec breakdown
* :func:`run_case`      — execute a single case (uses the LLM router)
* :func:`run_suite`     — execute a list of cases, return summary

Specs are simple, intentionally non-LLM checks (regex, JSON schema, length
bounds). LLM-judge scoring is a Phase 5 add-on.

Typical use::

    cases = [
        EvalCase(
            id="hook_short_001",
            category="llm.hook",
            messages=[
                {"role": "system", "content": "Write a 1-sentence hook."},
                {"role": "user",   "content": "Topic: Why pasta water is liquid gold"},
            ],
            spec=Spec(
                must_include_any=["pasta", "water"],
                must_not_include=["I can't", "as an AI"],
                max_chars=200,
                min_chars=20,
                json_schema=None,
            ),
        ),
    ]
    summary = await run_suite(cases)

The scaffold writes a JSON report to ``./prompt_eval_reports/<utc>.json``
so CI can diff against a baseline and fail the build on regressions.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import structlog

from src.providers.llm.base import LLMRequest

logger = structlog.get_logger()




@dataclass
class Spec:
    """Deterministic assertions for a single LLM output."""
    must_include_any: list[str] = field(default_factory=list)
    must_include_all: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    must_match_regex: list[str] = field(default_factory=list)
    min_chars: int = 0
    max_chars: int = 100_000
    json_required_keys: list[str] | None = None

    def evaluate(self, output: str) -> tuple[bool, list[str]]:
        failures: list[str] = []
        n = len(output or "")
        if n < self.min_chars:
            failures.append(f"len {n} < min_chars {self.min_chars}")
        if n > self.max_chars:
            failures.append(f"len {n} > max_chars {self.max_chars}")
        lc = (output or "").lower()
        if self.must_include_any:
            if not any(t.lower() in lc for t in self.must_include_any):
                failures.append(f"none of must_include_any={self.must_include_any} found")
        for term in self.must_include_all:
            if term.lower() not in lc:
                failures.append(f"missing must_include_all term: {term!r}")
        for term in self.must_not_include:
            if term.lower() in lc:
                failures.append(f"forbidden term present: {term!r}")
        for pattern in self.must_match_regex:
            if not re.search(pattern, output or "", flags=re.S | re.I):
                failures.append(f"regex did not match: {pattern!r}")
        if self.json_required_keys is not None:
            try:
                data = json.loads(output or "")
            except json.JSONDecodeError as exc:
                failures.append(f"output not valid JSON: {exc.msg}")
            else:
                if not isinstance(data, dict):
                    failures.append("JSON output is not an object")
                else:
                    for key in self.json_required_keys:
                        if key not in data:
                            failures.append(f"JSON missing required key: {key!r}")
        return (not failures), failures




@dataclass
class EvalCase:
    id: str
    category: str
    messages: list[dict]
    spec: Spec
    temperature: float = 0.3
    max_tokens: int = 800
    response_format: str = "text"


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    failures: list[str]
    output: str
    cost_usd: float
    latency_ms: int
    provider: str
    model: str

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "failures": self.failures,
            "output_excerpt": (self.output or "")[:500],
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": self.latency_ms,
            "provider": self.provider,
            "model": self.model,
        }




async def run_case(case: EvalCase, *, channel_id: str = "EVAL") -> EvalResult:
    """Run one case through the central LLM router."""
    from src.llm import route as _route

    start = time.monotonic()
    res = await _route(
        category=case.category,
        request=LLMRequest(
            messages=case.messages,
            temperature=case.temperature,
            max_tokens=case.max_tokens,
            response_format=case.response_format,
        ),
        channel_id=channel_id,
        content_id=f"eval-{case.id}",
        record_usage=False,
    )
    latency = int((time.monotonic() - start) * 1000)
    passed, failures = case.spec.evaluate(res.content)
    return EvalResult(
        case_id=case.id, passed=passed, failures=failures,
        output=res.content, cost_usd=res.cost_usd, latency_ms=latency,
        provider=res.provider, model=res.model,
    )


async def run_suite(
    cases: Iterable[EvalCase],
    *,
    channel_id: str = "EVAL",
    report_dir: str | Path = "prompt_eval_reports",
) -> dict[str, Any]:
    """Run a list of cases sequentially. Returns a summary dict.

    Sequential rather than gathered: keeps cost predictable for cron and
    avoids slamming a single provider with bursty traffic during evals.
    """
    results: list[EvalResult] = []
    total_cost = 0.0
    for case in cases:
        try:
            r = await run_case(case, channel_id=channel_id)
        except Exception as exc:
            logger.warning("prompt_eval.case_exception", case_id=case.id, error=str(exc))
            r = EvalResult(case_id=case.id, passed=False,
                           failures=[f"runtime exception: {exc}"],
                           output="", cost_usd=0.0, latency_ms=0,
                           provider="", model="")
        results.append(r)
        total_cost += r.cost_usd

    summary = {
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "total_cost_usd": round(total_cost, 6),
        "results": [r.as_dict() for r in results],
    }

    rd = Path(report_dir)
    rd.mkdir(parents=True, exist_ok=True)
    out_file = rd / (summary["ran_at_utc"].replace(":", "-") + ".json")
    out_file.write_text(json.dumps(summary, indent=2))
    logger.info("prompt_eval.suite_complete",
                passed=summary["passed"], failed=summary["failed"],
                cost=summary["total_cost_usd"], report=str(out_file))
    return summary
