"""Tier 1 foundation tests — v3.1 schema, prosody injector, word alignment,
provider registry lock, LLM router budget serialization.

These tests deliberately avoid live external dependencies (no Postgres,
no Redis, no ffprobe binary required). They exercise the pure-logic
pieces of the Tier 1 changes so we can catch regressions in CI without
needing the full docker-compose stack.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

# ──────────────────────── Direction v3.1 schema ────────────────────────


def test_v3_1_schema_accepts_v3_0_payload():
    """A v3.0 payload (no timeline/captions/micro_beats) parses under v3.1."""
    from contracts.direction_v3_1 import DirectionV3_1

    payload = {
        "version": "3.0",
        "meta": {
            "video_id": "vid_001",
            "channel_id": "ch_001",
            "title": "Test",
            "duration_target_seconds": 45,
            "aspect": "9:16",
            "fps": 30,
            "resolution": {"width": 1080, "height": 1920},
        },
        "template": "hybrid-kinetic",
        "theme": {
            "primary_color": "#000",
            "accent_color": "#fff",
            "background_color": "#111",
            "text_color": "#fff",
            "fonts": {"heading": "Inter", "body": "Inter"},
        },
        "grade_preset": "fx.grade.cinematic",
        "segments": [
            {
                "id": "s1",
                "start_ms": 0,
                "duration_ms": 5000,
                "scene_preset": "scene.placeholder",
            }
        ],
    }
    doc = DirectionV3_1.model_validate(payload)
    assert doc.version.value == "3.0"
    assert len(doc.segments) == 1
    assert doc.segments[0].timeline is None


def test_v3_1_density_validator_flags_gaps():
    """Consecutive keyframes > 500ms apart must be reported."""
    from contracts.direction_v3_1 import DirectionV3_1, validate_timeline_density

    payload = {
        "version": "3.1",
        "meta": {
            "video_id": "v",
            "channel_id": "c",
            "title": "t",
            "duration_target_seconds": 3,
            "aspect": "16:9",
            "fps": 30,
            "resolution": {"width": 1920, "height": 1080},
        },
        "template": "hybrid-kinetic",
        "theme": {
            "primary_color": "#000",
            "accent_color": "#fff",
            "background_color": "#111",
            "text_color": "#fff",
            "fonts": {"heading": "Inter", "body": "Inter"},
        },
        "grade_preset": "fx.grade.cinematic",
        "segments": [
            {
                "id": "s1",
                "start_ms": 0,
                "duration_ms": 3000,
                "scene_preset": "scene.placeholder",
                # 501ms gap between keyframes → should be flagged
                "timeline": [
                    {"t_ms": 0, "ease": "cubic-in-out"},
                    {"t_ms": 501, "ease": "cubic-in-out"},
                    {"t_ms": 1002, "ease": "cubic-in-out"},
                    {"t_ms": 2100, "ease": "cubic-in-out"},  # 1098ms gap
                    {"t_ms": 3000, "ease": "cubic-in-out"},
                ],
            }
        ],
    }
    doc = DirectionV3_1.model_validate(payload)
    issues = validate_timeline_density(doc)
    assert any("501" in i or "gap" in i.lower() for i in issues)
    assert any("1098" in i or "2100" in i for i in issues)


def test_v3_1_density_validator_passes_dense_timeline():
    from contracts.direction_v3_1 import DirectionV3_1, validate_timeline_density

    payload = {
        "version": "3.1",
        "meta": {
            "video_id": "v",
            "channel_id": "c",
            "title": "t",
            "duration_target_seconds": 3,
            "aspect": "16:9",
            "fps": 30,
            "resolution": {"width": 1920, "height": 1080},
        },
        "template": "hybrid-kinetic",
        "theme": {
            "primary_color": "#000",
            "accent_color": "#fff",
            "background_color": "#111",
            "text_color": "#fff",
            "fonts": {"heading": "Inter", "body": "Inter"},
        },
        "grade_preset": "fx.grade.cinematic",
        "segments": [
            {
                "id": "s1",
                "start_ms": 0,
                "duration_ms": 3000,
                "scene_preset": "scene.placeholder",
                # 500ms exactly is the floor — should pass
                "timeline": [{"t_ms": t, "ease": "cubic-in-out"} for t in range(0, 3001, 500)],
            }
        ],
    }
    doc = DirectionV3_1.model_validate(payload)
    assert validate_timeline_density(doc) == []


# ──────────────────────── Prosody injector ────────────────────────


def test_prosody_emphasis_instruction_zero_words():
    from media.prosody_injector import render_emphasis_instruction

    assert render_emphasis_instruction([]) == ""
    assert render_emphasis_instruction(["", "  "]) == ""


def test_prosody_emphasis_instruction_single_word():
    from media.prosody_injector import render_emphasis_instruction

    assert render_emphasis_instruction(["sleep"]) == "[speak with emphasis on sleep] "


def test_prosody_emphasis_instruction_multiple():
    from media.prosody_injector import render_emphasis_instruction

    out = render_emphasis_instruction(["sleep", "critical", "now"])
    assert out.startswith("[speak with emphasis on ")
    assert "sleep" in out and "critical" in out and "now" in out
    assert " and " in out  # oxford-style final connector


def test_prosody_emphasis_instruction_dedup_and_cap():
    from media.prosody_injector import render_emphasis_instruction

    # duplicates removed, capped at 6
    out = render_emphasis_instruction(["a", "A", "b", "c", "d", "e", "f", "g", "h"])
    assert out.count(",") + 1 <= 6  # 6 unique words maximum


def test_prosody_injection_full_order():
    from media.prosody_injector import ProsodyMarker, inject_prosody_markers

    m = ProsodyMarker(
        emphasis_words=["sleep"],
        pause_before_ms=200,
        pause_after_ms=300,
        opening_breath=True,
        closing_sigh=True,
        delivery_instruction="speak calmly",
    )
    out = inject_prosody_markers("Your body needs sleep.", m)
    # order: delivery → emphasis → breath → pause_before → sentence → pause_after → sigh
    assert out.index("[speak calmly]") < out.index("[speak with emphasis on sleep]")
    assert out.index("[speak with emphasis on sleep]") < out.index("[breath]")
    assert out.index("[breath]") < out.index("[pause 200ms]")
    assert out.index("[pause 200ms]") < out.index("Your body needs sleep.")
    assert out.index("Your body needs sleep.") < out.index("[pause 300ms]")
    assert out.index("[pause 300ms]") < out.index("[sigh]")


def test_prosody_injection_empty_sentence_returns_input():
    from media.prosody_injector import ProsodyMarker, inject_prosody_markers

    assert inject_prosody_markers("", ProsodyMarker(emphasis_words=["a"])) == ""
    assert inject_prosody_markers("   ", ProsodyMarker()) == "   "


def test_prosody_pause_cap():
    from media.prosody_injector import ProsodyMarker, inject_prosody_markers

    m = ProsodyMarker(pause_after_ms=99999)  # attempt to abuse
    out = inject_prosody_markers("Hi.", m)
    assert "[pause 3000ms]" in out  # capped at 3s


# ──────────────────────── Word-alignment normalizers ────────────────────────


def test_inworld_shape_a_timestamps_with_s_suffix():
    from media.word_alignment import normalize_inworld_alignment

    payload = {
        "timestamps": [
            {"text": "Sleep", "startTime": "0.120s", "endTime": "0.480s"},
            {"text": "matters", "startTime": "0.480s", "endTime": "0.900s"},
        ]
    }
    out = normalize_inworld_alignment(payload, segment_id="s1", emphasis_words=["Sleep"])
    assert len(out) == 2
    assert out[0].word == "Sleep"
    assert out[0].start_ms == 120
    assert out[0].end_ms == 480
    assert out[0].is_emphasis is True
    assert out[1].is_emphasis is False


def test_inworld_shape_b_words_seconds_floats():
    from media.word_alignment import normalize_inworld_alignment

    payload = {
        "words": [
            {"word": "Hi", "startTimeSeconds": 0.05, "endTimeSeconds": 0.22},
        ]
    }
    out = normalize_inworld_alignment(payload)
    assert len(out) == 1
    assert out[0].start_ms == 50
    assert out[0].end_ms == 220


def test_inworld_missing_returns_empty_list():
    from media.word_alignment import normalize_inworld_alignment

    assert normalize_inworld_alignment(None) == []
    assert normalize_inworld_alignment({}) == []
    assert normalize_inworld_alignment({"unknown_key": []}) == []


def test_whisperx_normalization():
    from media.word_alignment import normalize_whisperx_alignment

    payload = {
        "segments": [
            {
                "start": 0.0,
                "end": 1.5,
                "words": [
                    {"word": "Body", "start": 0.05, "end": 0.30, "score": 0.95},
                    {"word": "signals", "start": 0.30, "end": 0.75, "score": 0.88},
                ],
            }
        ]
    }
    out = normalize_whisperx_alignment(payload, segment_id="s2")
    assert len(out) == 2
    assert out[0].confidence == 0.95
    assert out[1].start_ms == 300
    assert out[1].segment_id == "s2"


def test_word_alignment_to_captions_offset():
    """When multiple sentences are concatenated, offset_ms shifts timings."""
    from media.word_alignment import (
        normalize_inworld_alignment,
        to_caption_words,
    )

    aligned = normalize_inworld_alignment({"timestamps": [{"text": "hi", "startTime": "0.1s", "endTime": "0.3s"}]})
    captions = to_caption_words(aligned, offset_ms=5000, style_id="cap.pop.yellow")
    assert captions[0].start_ms == 5100
    assert captions[0].end_ms == 5300
    assert captions[0].style_id == "cap.pop.yellow"


def test_word_alignment_end_before_start_gets_floor():
    from media.word_alignment import normalize_inworld_alignment

    payload = {"timestamps": [{"text": "x", "startTime": "0.5s", "endTime": "0.4s"}]}
    out = normalize_inworld_alignment(payload)
    assert len(out) == 1
    assert out[0].end_ms - out[0].start_ms == 50  # 50ms floor per word


# ──────────────────────── Provider registry lock ────────────────────────


def test_provider_registry_lock_exists():
    """The class-level cache is guarded by a threading lock."""
    from providers import registry

    assert hasattr(registry, "_INSTANCE_LOCK")
    import threading

    assert isinstance(registry._INSTANCE_LOCK, type(threading.Lock()))


def test_provider_registry_cache_returns_same_instance():
    """Repeated `get()` for the same key returns the cached instance."""
    from providers.registry import ProviderRegistry

    class FakeProvider:
        instances = 0

        def __init__(self):
            FakeProvider.instances += 1

    ProviderRegistry.reset()
    ProviderRegistry._registries.setdefault("fake_cat", {})["fake"] = FakeProvider

    a = ProviderRegistry.get("fake_cat", override="fake")
    b = ProviderRegistry.get("fake_cat", override="fake")
    assert a is b
    assert FakeProvider.instances == 1

    ProviderRegistry.reset()


# ──────────────────────── LLM router per-channel lock ────────────────────────


@pytest.mark.asyncio
async def test_router_serializes_per_channel_budget():
    """Two concurrent route() calls for the same channel serialize.

    We verify by having _spent_today reflect the previously-completed
    call's cost — under serialization the second call sees the first's
    write; under a race it would not.
    """
    from llm.router import Router

    from providers.llm.base import LLMResult

    calls_order: list[str] = []
    ledger: dict[str, float] = {"chan_a": 0.0}

    async def fake_cap(cid):
        return 100.0

    async def fake_spent(cid):
        return ledger.get(cid, 0.0)

    async def fake_content_mode(cid):
        return None

    async def fake_db_chain(*args, **kwargs):
        return []

    async def fake_record(*, content_id, channel_id, category, result):
        ledger[channel_id] = ledger.get(channel_id, 0.0) + result.cost_usd

    class FakeProvider:
        async def complete(self, req):
            calls_order.append("enter")
            await asyncio.sleep(0.05)
            calls_order.append("exit")
            return LLMResult(
                content="ok",
                model="fake",
                provider="fake",
                cost_usd=1.5,
                tokens_in=1,
                tokens_out=1,
                latency_ms=50,
            )

    with (
        patch("llm.router._cap_for", side_effect=fake_cap),
        patch("llm.router._spent_today", side_effect=fake_spent),
        patch("llm.router._content_mode_for", side_effect=fake_content_mode),
        patch("llm.router._db_chain_pairs", side_effect=fake_db_chain),
        patch("llm.router._record_usage", new=AsyncMock(side_effect=fake_record)),
        patch(
            "llm.router.ProviderRegistry.get",
            return_value=FakeProvider(),
        ),
    ):
        r = Router()
        from providers.llm.base import LLMRequest

        req = LLMRequest(messages=[{"role": "user", "content": "hi"}], model="fake")

        await asyncio.gather(
            r.route(category="llm", request=req, channel_id="chan_a"),
            r.route(category="llm", request=req, channel_id="chan_a"),
            r.route(category="llm", request=req, channel_id="chan_a"),
        )

    # Under serialization, calls_order MUST be strictly interleaved:
    # enter, exit, enter, exit, enter, exit — never enter, enter, ...
    for i in range(0, len(calls_order), 2):
        assert calls_order[i] == "enter"
        assert calls_order[i + 1] == "exit"
    assert ledger["chan_a"] == pytest.approx(4.5)


@pytest.mark.asyncio
async def test_router_different_channels_run_in_parallel():
    """Different channel_ids should NOT be serialized against each other."""
    from llm.router import Router

    from providers.llm.base import LLMRequest, LLMResult

    active_count = {"n": 0, "max": 0}

    async def fake_cap(cid):
        return 100.0

    async def fake_spent(cid):
        return 0.0

    async def fake_content_mode(cid):
        return None

    async def fake_db_chain(*args, **kwargs):
        return []

    class FakeProvider:
        async def complete(self, req):
            active_count["n"] += 1
            active_count["max"] = max(active_count["max"], active_count["n"])
            await asyncio.sleep(0.05)
            active_count["n"] -= 1
            return LLMResult(
                content="ok",
                model="fake",
                provider="fake",
                cost_usd=0.1,
                tokens_in=1,
                tokens_out=1,
                latency_ms=50,
            )

    with (
        patch("llm.router._cap_for", side_effect=fake_cap),
        patch("llm.router._spent_today", side_effect=fake_spent),
        patch("llm.router._content_mode_for", side_effect=fake_content_mode),
        patch("llm.router._db_chain_pairs", side_effect=fake_db_chain),
        patch("llm.router._record_usage", new=AsyncMock(return_value=None)),
        patch(
            "llm.router.ProviderRegistry.get",
            return_value=FakeProvider(),
        ),
    ):
        r = Router()
        req = LLMRequest(messages=[{"role": "user", "content": "hi"}], model="fake")

        await asyncio.gather(
            r.route(category="llm", request=req, channel_id="chan_a"),
            r.route(category="llm", request=req, channel_id="chan_b"),
            r.route(category="llm", request=req, channel_id="chan_c"),
        )

    assert active_count["max"] >= 2, "Different channels should run in parallel"


# ──────────────────────── Events / Streams API surface ────────────────────────


def test_streams_module_public_api():
    """Streams adapter exposes the promised functions."""
    from events import consume_stream, publish_dual_write, publish_stream

    assert callable(publish_stream)
    assert callable(publish_dual_write)
    assert callable(consume_stream)


def test_streams_stream_key_format():
    from events.streams import STREAM_PREFIX, _stream_key

    assert _stream_key("brain.directive") == f"{STREAM_PREFIX}brain.directive"
    assert STREAM_PREFIX == "stream:"
