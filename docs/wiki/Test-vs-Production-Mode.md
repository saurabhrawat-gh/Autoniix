# Test vs Production Mode

## Purpose

A single global toggle flips the entire pipeline between a free, fast,
low-fidelity “test” mode and the paid, full-quality “production” mode —
without restarting any service.

## Source

- `src/environment.py:1-135`
- `src/providers/registry.py:30-45` (test-mode provider remap)
- `src/services/dashboard/v2/system.py` (`/system/environment`)
- `docs/07-TEST-VS-PRODUCTION.md` (long-form)

## Mode resolution

```python
get_mode():
  return (
    _db_mode_override                       # set by dashboard toggle
    or _cached_db_mode  if cache fresh
    or settings.environment_mode            # ENVIRONMENT_MODE env var
    or "test"
  )
```

Cache TTL is 5 seconds so a toggle propagates fleet-wide within ~5s.

## Differences

| Aspect | test | production |
|---|---|---|
| LLMs | mock_llm (cached + GPT-4o-mini fallback) | real (gpt-4o, claude, gemini) |
| TTS | edge_tts (free) | fishaudio (default) |
| Images | placeholder (Pillow) | dalle |
| Search | mock_search (cache + Wikipedia) | serpapi |
| Storage prefix | `test/` | `prod/` |
| Content id prefix | `TEST_VID_*` | `VID_*` |
| Render resolution | 640×360 @ 15fps | 1920×1080 @ 30fps |
| YouTube upload | **disabled** (simulated) | enabled |
| Quality gates | all set to 0 | full thresholds |
| Daily budget cap | $5 | configurable |
| Daily video cap | 10 | configurable |

## Database tagging

`videos.environment`, `feedback_loop.environment`, `job_events.environment`
all carry the mode value, so test data never pollutes production
analytics. The clean-slate endpoint relies on this tagging.

## UI affordances

- Header pill: green TEST or red pulsing PRODUCTION.
- Production toggle requires a confirmation dialog listing financial
  impact + an explicit confirmation phrase.
- Banners across every page that mention writes (Trigger, Settings,
  Clean-slate) reiterate the mode.

## Related pages

- [[BFF-System-And-FleetHealth]] · [[Architecture-Provider-Pattern]] ·
  [[Cost-Analysis]]
