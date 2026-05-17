# Providers: TTS

## Purpose

Text-to-speech with a unified emotion-knob interface so the voice service
stays vendor-neutral.

## Source

- `src/providers/tts/base.py`
- `src/providers/tts/fish_audio.py` (default in production)
- `src/providers/tts/elevenlabs_provider.py`
- `src/providers/tts/edge_tts_provider.py` (free, test-mode default)

## ABC

```python
class TTSProvider(ABC):
    async def synthesize(text, voice_id) -> bytes: ...
    async def synthesize_with_params(
        text, voice_id, *,
        stability,         # 0–1  — lower = more dynamic
        similarity_boost,  # 0–1  — voice cloning fidelity
        style,             # 0–1  — expressiveness
        speed,             # 0.5–2.0
    ) -> bytes: ...
    def estimate_cost(text) -> float: ...
    async def health_check() -> bool: ...
    def provider_name() -> str: ...
    async def get_word_timestamps(audio_bytes, text) -> list[dict] | None
```

## Provider mapping

| Knob | Fish Audio | ElevenLabs | Edge TTS |
|---|---|---|---|
| stability | `stability` 0–1 | `stability` 0–1 | rate ± 50% mapping |
| similarity_boost | `similarity` | `similarity_boost` | n/a |
| style | `temperature` | `style` | `style` SSML tag |
| speed | `speed` | `speed` (SSML wrap) | `rate` |

Each provider mediates the differences in its own implementation; the
voice service never sees vendor-specific params.

## Cost

| Provider | Cost per minute |
|---|---|
| Fish Audio | ~$0.0208 |
| ElevenLabs | ~$0.18 |
| Edge TTS | $0.00 |

## Word timestamps

Used by the editor service for captioning and by the assembly service for
voice-text alignment validation. Fish Audio and ElevenLabs both support
this; Edge TTS returns `None` and the editor falls back to a forced
aligner on the audio file.

## Related pages

- [[Service-Voice]] · [[Architecture-Provider-Pattern]]
