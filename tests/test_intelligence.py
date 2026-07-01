"""Tests for Phase 5 intelligence layer.

Covers:
* Niche-template loader — schema validation, lookup, caching
* Performance feedback formatter — output shape on cold-start, top-only,
  worst-only, mixed; defensive handling of missing fields.

The DB-touching ``build_performance_context`` is exercised via the
``_format_for_tests`` shim so these tests stay pure-function.
"""
from __future__ import annotations

import pytest

from src.intelligence import niche_templates as nt
from src.intelligence.performance_feedback import _format_for_tests




def test_list_templates_returns_nonempty_list():
    out = nt.list_templates()
    assert isinstance(out, list)
    assert len(out) >= 4, "expected several starter presets"


def test_every_template_has_required_fields():
    """Every template must be drop-in-ready for the channels API.

    Missing keys here would mean a wizard click silently produces a
    half-configured channel — exactly the kind of bug presets are meant to
    eliminate.
    """
    required_top = {"id", "label", "niche", "summary", "dna"}
    required_dna = {
        "belief_territory", "intellectual_lens", "topic_domain",
        "brand_voice", "narrative_rhythm", "emotional_contract",
        "target_audience", "primary_format_long", "primary_format_short",
        "thumbnail_style", "primary_color", "forbidden_words",
    }
    for t in nt.list_templates():
        missing_top = required_top - t.keys()
        assert not missing_top, f"template {t.get('id')!r} missing {missing_top}"
        missing_dna = required_dna - t["dna"].keys()
        assert not missing_dna, f"template {t['id']!r} dna missing {missing_dna}"


def test_template_ids_are_unique():
    ids = [t["id"] for t in nt.list_templates()]
    assert len(ids) == len(set(ids))


def test_get_template_by_id():
    sample = nt.list_templates()[0]
    got = nt.get_template(sample["id"])
    assert got is not None
    assert got["id"] == sample["id"]


def test_get_template_unknown_returns_none():
    assert nt.get_template("does_not_exist_xyz") is None


def test_list_templates_returns_copies_not_internal_state():
    """The loader caches the parsed JSON — callers must not be able to
    mutate that cache by editing returned dicts."""
    a = nt.list_templates()
    a[0]["label"] = "MUTATED"
    b = nt.list_templates()
    assert b[0]["label"] != "MUTATED"




def test_format_empty_returns_empty_string():
    """Cold-start channels (no analytics yet) get no prompt context.

    Critical: an empty-but-formatted block would cost tokens for nothing
    and confuse the model with placeholders.
    """
    assert _format_for_tests({"top": [], "worst": [], "stats": {}}) == ""
    assert _format_for_tests({}) == ""


def test_format_includes_top_performers():
    out = _format_for_tests({
        "top": [
            {"title": "Why pasta water is liquid gold",
             "yt_views": 120_000, "engagement_rate": 7.5,
             "performance_tier": "S"},
        ],
        "worst": [],
        "stats": {"n": 1, "avg_views": 120_000, "avg_engagement": 7.5},
    })
    assert "WHAT WORKS" in out
    assert "120,000" in out, "view counts should be human-formatted"
    assert "[S]" in out
    assert "pasta water" in out
    assert "WHAT FLOPS" not in out, "no flops section when worst is empty"


def test_format_includes_worst_performers():
    out = _format_for_tests({
        "top": [],
        "worst": [
            {"title": "A boring rant",
             "yt_views": 800, "engagement_rate": 0.4,
             "performance_tier": "D"},
        ],
        "stats": {},
    })
    assert "WHAT FLOPS" in out
    assert "boring rant" in out
    assert "WHAT WORKS" not in out


def test_format_truncates_long_titles():
    long_title = "x" * 500
    out = _format_for_tests({
        "top": [{"title": long_title, "yt_views": 50_000,
                 "engagement_rate": 5.0, "performance_tier": "A"}],
        "worst": [], "stats": {},
    })
    assert "x" * 500 not in out
    assert "x" * 100 in out


def test_format_handles_none_fields_gracefully():
    """Real DB rows can have NULLs; the formatter must not crash."""
    out = _format_for_tests({
        "top": [{"title": None, "yt_views": None,
                 "engagement_rate": None, "performance_tier": None}],
        "worst": [], "stats": {},
    })
    assert "WHAT WORKS" in out
    assert "0 views" in out


def test_format_includes_baseline_stats_when_available():
    out = _format_for_tests({
        "top": [{"title": "ok", "yt_views": 10_000,
                 "engagement_rate": 4.0, "performance_tier": "B"}],
        "worst": [],
        "stats": {"n": 12, "avg_views": 8_500, "avg_engagement": 3.7},
    })
    assert "12 measured videos" in out
    assert "8,500 views" in out
