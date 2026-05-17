# Service: Voice

## Purpose

Turns the script’s voice representation (per-sentence SSML + prosody hints)
into narration audio. Provider-agnostic via the TTS ABC.

## Port / source

- Port `8003`, memory 768M
- `src/services/voice/main.py`
- Intelligence modules:
  - `emotion_predictor.py`
  - `audio_quality_scorer.py`
  - `voice_style_learner.py` (GBM for TTS params per niche)

## Provider chain (production default)

1. Fish Audio (PAYG ~$0.0208/min, 77–89% cheaper than ElevenLabs)
2. ElevenLabs (`eleven_multilingual_v2`)
3. Edge TTS (free) — also the test-mode default

All implement `synthesize_with_params(text, voice_id, *, stability,
similarity_boost, style, speed)`. Each provider maps the abstract knobs to
its native API. See [[Providers-TTS]].

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /synthesize` | Single-segment TTS |
| `POST /synthesize-script` | Whole script with per-segment params |
| `POST /score-audio` | Quality scorer (loudness, sibilance, pacing) |
| `POST /voice-feedback` | Outcome ingest |
| `POST /voice-train` | Retrain `voice_style_gbm` |

## Emotion map

Per sentence the script declares an emotion tag (e.g. `curious`,
`urgent`, `reassuring`). `emotion_predictor` plus the GBM produces:

```json
{
  "stability": 0.45,
  "similarity_boost": 0.85,
  "style": 0.32,
  "speed": 1.05,
  "emphasis_words": ["never", "again"],
  "volume_shift": +1.5
}
```

## Output

WAV/MP3 uploaded to `s3://autoniix/<prefix>/voice/<content_id>/<segment>.mp3`
plus word-level timestamps if the provider supports them (used for caption
generation in editor).

## Related pages

- [[Providers-TTS]]
- [[Service-Script]]
- [[Service-Editor]]
