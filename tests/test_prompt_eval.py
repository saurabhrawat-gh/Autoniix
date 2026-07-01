"""Tests for the prompt-eval scaffold's deterministic Spec engine.

The actual LLM-driven runs live in ``scripts/run_prompt_eval.py`` and are
exercised in CI's e2e job. Here we only assert that the spec engine
correctly translates assertions into pass/fail decisions — no LLM calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.quality.prompt_eval import EvalCase, Spec


CASES_DIR = Path(__file__).parent / "prompt_eval" / "cases"


def test_spec_passes_clean_output():
    spec = Spec(
        must_include_any=["pasta", "water"],
        must_not_include=["as an AI"],
        min_chars=20, max_chars=200,
    )
    output = "Pasta water is the cheapest finishing trick in any kitchen."
    ok, failures = spec.evaluate(output)
    assert ok is True
    assert failures == []


def test_spec_flags_too_short():
    spec = Spec(min_chars=50, max_chars=200)
    ok, failures = spec.evaluate("nope")
    assert not ok
    assert any("min_chars" in f for f in failures)


def test_spec_flags_forbidden_term():
    spec = Spec(must_not_include=["as an AI"])
    ok, failures = spec.evaluate("As an AI language model, I cannot...")
    assert not ok
    assert any("forbidden term" in f for f in failures)


def test_spec_requires_at_least_one_of():
    spec = Spec(must_include_any=["pasta", "water"])
    ok, failures = spec.evaluate("This is about cars.")
    assert not ok
    assert any("must_include_any" in f for f in failures)


def test_spec_must_include_all_terms():
    spec = Spec(must_include_all=["pasta", "starchy"])
    ok, failures = spec.evaluate("Pasta water is liquid gold.")
    assert not ok
    assert any("starchy" in f for f in failures)


def test_spec_validates_json_keys():
    spec = Spec(json_required_keys=["title", "summary"])
    ok, failures = spec.evaluate('{"title": "Hi", "summary": "Yes"}')
    assert ok is True
    ok2, failures2 = spec.evaluate('{"title": "Hi"}')
    assert not ok2
    assert any("summary" in f for f in failures2)


def test_spec_handles_invalid_json():
    spec = Spec(json_required_keys=["title"])
    ok, failures = spec.evaluate("not json at all")
    assert not ok
    assert any("not valid JSON" in f for f in failures)


def test_regex_match_required():
    spec = Spec(must_match_regex=[r"^\d{4}"])
    ok, _ = spec.evaluate("2026 is the year")
    assert ok is True
    ok2, failures = spec.evaluate("twenty twenty six")
    assert not ok2
    assert any("regex" in f for f in failures)


def test_example_case_file_loads_cleanly():
    """The seed case under ``tests/prompt_eval/cases`` must parse and the
    embedded spec must round-trip into the dataclass without loss."""
    p = CASES_DIR / "hook_short_001.json"
    raw = json.loads(p.read_text())
    spec = Spec(**raw["spec"])
    case = EvalCase(
        id=raw["id"], category=raw["category"],
        messages=raw["messages"], spec=spec,
        temperature=raw.get("temperature", 0.3),
        max_tokens=raw.get("max_tokens", 800),
        response_format=raw.get("response_format", "text"),
    )
    assert case.id == "hook_short_001"
    ok, failures = case.spec.evaluate("")
    assert not ok
    assert any("min_chars" in f for f in failures)
