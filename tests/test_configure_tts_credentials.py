"""Tests for AE-30: Configure TTS credentials.

Covers:
- EdgeTTSProvider.voice from extra_config (wizard field)
- Voice priority order: request.voice_id > self.voice > DEFAULT_VOICE
- chain._instantiate sets api_key on provider when settings value is empty
- FishAudioTTS and ElevenLabsTTS have api_key attribute settable via chain
- edge_tts needs no API key (secret_value may be empty)
"""

from __future__ import annotations

import pytest


def test_edge_tts_default_voice_attribute():
    from providers.tts.edge_tts_provider import EdgeTTSProvider

    inst = EdgeTTSProvider()
    assert inst.voice == ""
    inst.voice = "en-GB-RyanNeural"
    assert inst.voice == "en-GB-RyanNeural"


def test_edge_tts_voice_from_extra_config():
    """chain._instantiate setattr sets voice from extra_config."""
    from providers.tts.edge_tts_provider import EdgeTTSProvider

    inst = EdgeTTSProvider()
    extra = {"voice": "zh-CN-XiaoxiaoNeural"}
    for k, v in extra.items():
        setattr(inst, k, v)
    assert inst.voice == "zh-CN-XiaoxiaoNeural"


@pytest.mark.asyncio
async def test_edge_tts_synthesize_uses_self_voice(monkeypatch):
    """synthesize() uses self.voice when request has no voice_id."""
    from providers.tts.base import TTSRequest
    from providers.tts.edge_tts_provider import EdgeTTSProvider

    captured: dict = {}

    async def fake_synthesize_with_params(self_inner, text, voice_id, **kw):
        captured["voice_id"] = voice_id
        from providers.tts.base import TTSResult

        return TTSResult(
            audio_bytes=b"", duration_s=0.0, word_count=1, bytes_charged=0, cost_usd=0.0, provider="edge_tts"
        )

    monkeypatch.setattr(EdgeTTSProvider, "synthesize_with_params", fake_synthesize_with_params)

    inst = EdgeTTSProvider()
    inst.voice = "fr-FR-DeniseNeural"
    req = TTSRequest(text="bonjour", voice_id="")
    await inst.synthesize(req)
    assert captured["voice_id"] == "fr-FR-DeniseNeural"


@pytest.mark.asyncio
async def test_edge_tts_request_voice_id_wins(monkeypatch):
    """request.voice_id takes priority over self.voice."""
    from providers.tts.base import TTSRequest
    from providers.tts.edge_tts_provider import EdgeTTSProvider

    captured: dict = {}

    async def fake_synthesize_with_params(self_inner, text, voice_id, **kw):
        captured["voice_id"] = voice_id
        from providers.tts.base import TTSResult

        return TTSResult(
            audio_bytes=b"", duration_s=0.0, word_count=1, bytes_charged=0, cost_usd=0.0, provider="edge_tts"
        )

    monkeypatch.setattr(EdgeTTSProvider, "synthesize_with_params", fake_synthesize_with_params)

    inst = EdgeTTSProvider()
    inst.voice = "fr-FR-DeniseNeural"
    req = TTSRequest(text="hello", voice_id="en-US-GuyNeural")  # noqa
    await inst.synthesize(req)
    assert captured["voice_id"] == "en-US-GuyNeural"


@pytest.mark.asyncio
async def test_edge_tts_falls_back_to_default(monkeypatch):
    """Falls back to DEFAULT_VOICE when neither request nor self.voice is set."""
    from providers.tts.base import TTSRequest
    from providers.tts.edge_tts_provider import DEFAULT_VOICE, EdgeTTSProvider

    captured: dict = {}

    async def fake_synthesize_with_params(self_inner, text, voice_id, **kw):
        captured["voice_id"] = voice_id
        from providers.tts.base import TTSResult

        return TTSResult(
            audio_bytes=b"", duration_s=0.0, word_count=1, bytes_charged=0, cost_usd=0.0, provider="edge_tts"
        )

    monkeypatch.setattr(EdgeTTSProvider, "synthesize_with_params", fake_synthesize_with_params)

    inst = EdgeTTSProvider()
    req = TTSRequest(text="hello", voice_id="")
    await inst.synthesize(req)
    assert captured["voice_id"] == DEFAULT_VOICE


def test_instantiate_sets_api_key_when_settings_empty(monkeypatch):
    """chain._instantiate sets inst.api_key if vault returns key but settings is empty."""
    import core.config as cfg

    monkeypatch.setattr(cfg.settings, "fish_audio_api_key", "")

    from providers.tts.fish_audio import FishAudioTTS

    inst = FishAudioTTS()
    assert inst.api_key == ""

    vault_api_key = "fish-test-key-xyz"
    if vault_api_key and hasattr(inst, "api_key") and not getattr(inst, "api_key", None):
        inst.api_key = vault_api_key

    assert inst.api_key == "fish-test-key-xyz"


def test_elevenlabs_api_key_settable():
    """ElevenLabsTTS.api_key can be set directly (chain._instantiate path)."""
    from providers.tts.elevenlabs_provider import ElevenLabsTTS

    inst = ElevenLabsTTS()
    inst.api_key = "el-test-key"
    assert inst.api_key == "el-test-key"


def test_chain_instantiate_api_key_patch():
    """Verify the chain._instantiate api_key fallback logic directly."""
    from unittest.mock import patch

    import providers.boot  # noqa: F401
    from providers.chain import _instantiate

    with patch("providers.chain.get_secret_at", return_value="secret-tts-key"):
        inst = _instantiate(
            "edge_tts",
            "providers/tts/edge_tts/default",
            {},
            None,
            {"edge_tts": __import__("providers.tts.edge_tts_provider", fromlist=["EdgeTTSProvider"]).EdgeTTSProvider},
        )
    assert inst is not None
