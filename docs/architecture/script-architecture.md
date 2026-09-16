# Script Architecture — Three Views

> Single canonical script → three deterministic views: Voiceover, Assets, Remotion Direction v3

---

## Overview

Every video starts with a **canonical script** (single source of truth). Three **view transforms** derive task-specific representations from it. The transforms are pure functions — same input always produces the same output.

```
                        ┌─────────────────────┐
                        │  Script Service      │
                        │  (Claude Sonnet)     │
                        │                      │
                        │  Produces:           │
                        │  script_base.json    │
                        └──────────┬──────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 │                 │                  │
         ┌───────▼──────┐  ┌──────▼───────┐  ┌──────▼───────────┐
         │ View A:       │  │ View B:       │  │ View C:           │
         │ Voiceover     │  │ Assets        │  │ Remotion v3       │
         │               │  │               │  │                   │
         │ → Voice Svc   │  │ → Assets Svc  │  │ → Assembly Svc    │
         │   (TTS)       │  │   (Stock/SFX) │  │   → Render Svc    │
         └───────────────┘  └───────────────┘  └───────────────────┘
```

---

## Canonical Script Model (`script_base.json`)

This is the authoritative representation. All views derive from it.

```json
{
  "script_id": "VID_BS001_20250425_001",
  "channel_id": "BS001",
  "content_mode": "long_form",
  "title": "4 Types of Shivers Your Body Produces (And What Each Means)",
  "hook_variant": {
    "id": "h1",
    "text": "Right now, your muscles are doing something you can't feel.",
    "style": "curiosity_gap"
  },
  "metadata": {
    "description": "Your body shivers for 4 very different reasons...",
    "tags": ["body shivers", "why do we shiver", "body signals", "health facts"],
    "category": "Science & Technology",
    "target_wpm": 150,
    "target_duration_s": 480,
    "word_count": 1087,
    "estimated_duration_s": 435
  },
  "scenes": [
    {
      "id": "s1",
      "index": 0,
      "role": "narration",
      "section": "hook",
      "text_raw": "Right now, your muscles are doing something you can't feel. Tiny fibers are contracting and relaxing — twenty times every second. And when your brain decides it's time to turn up the heat... that's when you feel it.",
      "claims": [
        {
          "text": "muscles contract 20 times per second during shivering",
          "confidence": 0.92,
          "source": "https://pubmed.ncbi.nlm.nih.gov/12345",
          "source_type": "peer_reviewed",
          "requires_disclaimer": false
        }
      ],
      "visual_intents": [
        "microscopic muscle fiber contraction",
        "cold weather breath vapor",
        "body heat visualization"
      ],
      "pace_hint": "slow_build",
      "emotion": "curious",
      "emphasis_words": ["muscles", "twenty times", "heat"],
      "duration_hint_s": 15,
      "visual_only": false
    },
    {
      "id": "s2",
      "index": 1,
      "role": "narration",
      "section": "explain",
      "text_raw": "Shivering is your body's emergency furnace. When core temperature drops below 36.1°C, your hypothalamus triggers rapid muscle contractions to generate heat.",
      "claims": [
        {
          "text": "hypothalamus triggers shivering below 36.1°C",
          "confidence": 0.95,
          "source": "https://www.ncbi.nlm.nih.gov/...",
          "source_type": "peer_reviewed",
          "requires_disclaimer": false
        }
      ],
      "visual_intents": ["thermometer dropping", "brain hypothalamus highlighted", "furnace igniting"],
      "pace_hint": "normal",
      "emotion": "informative",
      "emphasis_words": ["emergency furnace", "36.1°C", "hypothalamus"],
      "duration_hint_s": 12,
      "visual_only": false
    },
    {
      "id": "s3",
      "index": 2,
      "role": "broll_only",
      "section": "transition",
      "text_raw": "",
      "claims": [],
      "visual_intents": ["cold mountain landscape wide shot"],
      "pace_hint": "slow",
      "emotion": null,
      "emphasis_words": [],
      "duration_hint_s": 3,
      "visual_only": true
    }
  ],
  "structure": {
    "sections": [
      { "name": "hook", "scenes": ["s1"], "target_pct": 8 },
      { "name": "problem", "scenes": ["s2", "s3"], "target_pct": 15 },
      { "name": "explain", "scenes": [], "target_pct": 50 },
      { "name": "reveal", "scenes": [], "target_pct": 20 },
      { "name": "cta", "scenes": [], "target_pct": 7 }
    ]
  },
  "scores": {
    "structure": 8.5,
    "engagement": 8.8,
    "accuracy": 9.1,
    "brand_voice": 8.3,
    "hook_retention": 8.9,
    "overall": 8.6
  }
}
```

### Field Reference

| Field                       | Type   | Required | Notes                                                                                    |
| --------------------------- | ------ | -------- | ---------------------------------------------------------------------------------------- |
| `scenes[].id`               | string | yes      | Unique within script                                                                     |
| `scenes[].role`             | enum   | yes      | `narration` \| `broll_only` \| `on_screen_text`                                          |
| `scenes[].section`          | string | yes      | Which structural section this belongs to                                                 |
| `scenes[].text_raw`         | string | yes      | Authoritative narration text (empty if `visual_only`)                                    |
| `scenes[].claims[]`         | array  | yes      | Fact claims for verification; empty if no claims                                         |
| `scenes[].visual_intents[]` | array  | yes      | High-level descriptions for asset search                                                 |
| `scenes[].pace_hint`        | enum   | yes      | `slow_build` \| `slow` \| `normal` \| `fast` \| `urgent`                                 |
| `scenes[].emotion`          | string | nullable | `curious` \| `serious` \| `excited` \| `dramatic` \| `calm` \| `urgent` \| `informative` |
| `scenes[].emphasis_words[]` | array  | yes      | Words to highlight in captions / kinetic text                                            |
| `scenes[].duration_hint_s`  | float  | yes      | Estimated scene duration                                                                 |
| `scenes[].visual_only`      | bool   | yes      | If true, no TTS for this scene                                                           |

---

## View A: Voiceover Script (`script_voice.json`)

### Purpose

Feed to Voice Service for TTS generation. Contains only narrated scenes with emotion cues and pronunciation hints.

### Transform Rules

1. **Filter:** Remove scenes where `visual_only == true`
2. **Tone cues:** Prepend emotion-aware phrasing based on `emotion` and `pace_hint`
3. **Sentence split:** Break `text_raw` into sentences for per-sentence TTS (better timing)
4. **Emphasis:** Mark `emphasis_words` for the TTS provider (Fish Audio uses text cues; ElevenLabs uses SSML)
5. **Normalize:** Strip brackets, stage directions, normalize punctuation
6. **Ordering:** Maintain scene index order

### Transform Function (Python)

```python
def transform_voice_view(script_base: dict, voice_config: dict) -> dict:
    """Pure function: script_base → script_voice.json"""

    TONE_CUES = {
        "curious": "[speaking with curiosity] ",
        "serious": "[speaking seriously] ",
        "excited": "[speaking with excitement] ",
        "dramatic": "[speaking dramatically] ",
        "calm": "[speaking calmly] ",
        "urgent": "[speaking urgently] ",
        "informative": "",
    }

    PACE_MAP = {
        "slow_build": 130,
        "slow": 120,
        "normal": 150,
        "fast": 170,
        "urgent": 180,
    }

    scenes = []
    for scene in script_base["scenes"]:
        if scene["visual_only"]:
            continue

        # Add tone cue for Fish Audio (responds to text-level cues)
        tone_prefix = TONE_CUES.get(scene.get("emotion"), "")
        text = tone_prefix + scene["text_raw"]

        # Split into sentences for per-sentence timing
        sentences = split_sentences(text)

        scenes.append({
            "id": scene["id"],
            "text": text,
            "sentences": sentences,
            "emotion": scene.get("emotion"),
            "emphasis": scene.get("emphasis_words", []),
            "pace_wpm": PACE_MAP.get(scene.get("pace_hint"), voice_config.get("target_wpm", 150)),
            "duration_hint_s": scene["duration_hint_s"],
        })

    return {
        "script_id": script_base["script_id"],
        "channel_id": script_base["channel_id"],
        "voice_config": voice_config,
        "scenes": scenes,
        "total_word_count": sum(len(s["text"].split()) for s in scenes),
    }
```

### Output Schema

```json
{
  "script_id": "VID_BS001_20250425_001",
  "channel_id": "BS001",
  "voice_config": {
    "provider": "fish_audio",
    "voice_id": "ref_abc123",
    "target_wpm": 150,
    "format": "mp3",
    "bitrate": 128,
    "normalize": true
  },
  "scenes": [
    {
      "id": "s1",
      "text": "[speaking with curiosity] Right now, your muscles are doing something you can't feel. Tiny fibers are contracting and relaxing — twenty times every second. And when your brain decides it's time to turn up the heat... that's when you feel it.",
      "sentences": [
        "Right now, your muscles are doing something you can't feel.",
        "Tiny fibers are contracting and relaxing — twenty times every second.",
        "And when your brain decides it's time to turn up the heat... that's when you feel it."
      ],
      "emotion": "curious",
      "emphasis": ["muscles", "twenty times", "heat"],
      "pace_wpm": 130,
      "duration_hint_s": 15
    }
  ],
  "total_word_count": 42
}
```

### Quality Gates (Voice View)

| Gate                              | Threshold                          | Action on Fail  |
| --------------------------------- | ---------------------------------- | --------------- |
| Word count matches base           | 100% of narrated words             | Regenerate view |
| No empty text for narrated scenes | 0 empty                            | Block           |
| Sentence split valid              | All sentences end with punctuation | Fix punctuation |
| Pace WPM in range                 | 120-180                            | Clamp to range  |

---

## View B: Asset-Generation Script (`script_assets.json`)

### Purpose

Feed to Assets Service for stock footage, music, and SFX sourcing. Contains search terms, timing, and style requirements.

### Transform Rules

1. **Extract search terms:** From `visual_intents` + key nouns/verbs from `text_raw`
2. **Compute durations:** From `duration_hint_s` (or TTS duration if available)
3. **Style inference:** Map `pace_hint` and `emotion` to visual style preferences
4. **Music mood curve:** Aggregate scene emotions into a mood timeline
5. **SFX triggers:** Identify moments where SFX would enhance (transitions, emphasis)
6. **Diversity rules:** Ensure minimum 3 visual styles across scenes

### Transform Function (Python)

```python
def transform_assets_view(script_base: dict, voice_result: dict = None) -> dict:
    """Pure function: script_base + optional voice timing → script_assets.json"""

    STYLE_MAP = {
        "curious": "cinematic_wonder",
        "serious": "documentary",
        "excited": "dynamic_fast",
        "dramatic": "cinematic_dark",
        "calm": "nature_serene",
        "urgent": "news_style",
        "informative": "educational",
    }

    assets = []
    mood_curve = []
    sfx_triggers = []

    for scene in script_base["scenes"]:
        # Get actual duration from voice result if available
        duration = scene["duration_hint_s"]
        if voice_result:
            voice_scene = next((v for v in voice_result["scenes"] if v["id"] == scene["id"]), None)
            if voice_scene and voice_scene.get("duration_s"):
                duration = voice_scene["duration_s"]

        # Extract search terms from visual intents + text nouns
        search_terms = scene.get("visual_intents", [])
        if scene["text_raw"]:
            search_terms += extract_key_nouns(scene["text_raw"])

        # Deduplicate and limit
        search_terms = deduplicate(search_terms)[:5]

        style = STYLE_MAP.get(scene.get("emotion"), "educational")

        assets.append({
            "scene_id": scene["id"],
            "search_terms": search_terms,
            "min_resolution": "1280x720",
            "duration_s": duration,
            "style_preference": style,
            "visual_only": scene["visual_only"],
        })

        # Build mood curve
        if scene.get("emotion"):
            mood_curve.append(scene["emotion"])

        # SFX at scene transitions
        if scene["index"] > 0 and scene.get("pace_hint") in ("fast", "urgent"):
            sfx_triggers.append({
                "scene_id": scene["id"],
                "type": "whoosh",
                "at_s": 0.0,
            })

    return {
        "script_id": script_base["script_id"],
        "channel_id": script_base["channel_id"],
        "assets": assets,
        "music_config": {
            "mood_curve": mood_curve,
            "bpm_target": compute_bpm(mood_curve),
            "genre": "ambient_cinematic",
            "duration_s": sum(a["duration_s"] for a in assets),
        },
        "sfx_triggers": sfx_triggers,
    }
```

### Output Schema

```json
{
  "script_id": "VID_BS001_20250425_001",
  "channel_id": "BS001",
  "assets": [
    {
      "scene_id": "s1",
      "search_terms": [
        "microscopic muscle fiber contraction",
        "cold weather breath vapor",
        "body heat visualization",
        "muscles",
        "fibers"
      ],
      "min_resolution": "1280x720",
      "duration_s": 15,
      "style_preference": "cinematic_wonder",
      "visual_only": false
    },
    {
      "scene_id": "s3",
      "search_terms": ["cold mountain landscape wide shot"],
      "min_resolution": "1280x720",
      "duration_s": 3,
      "style_preference": "nature_serene",
      "visual_only": true
    }
  ],
  "music_config": {
    "mood_curve": ["curious", "informative"],
    "bpm_target": 92,
    "genre": "ambient_cinematic",
    "duration_s": 480
  },
  "sfx_triggers": []
}
```

### Quality Gates (Assets View)

| Gate                                    | Threshold        | Action on Fail                 |
| --------------------------------------- | ---------------- | ------------------------------ |
| Every scene has ≥1 search term          | 100%             | Extract from text_raw fallback |
| Total duration matches script           | ±10%             | Adjust proportionally          |
| Min 3 visual styles                     | ≥3 unique styles | Add variety                    |
| No duplicate search terms across scenes | <30% overlap     | Deduplicate                    |

---

## View C: Remotion Direction v3 (`script_remotion.json`)

### Purpose

The Assembly Service generates this from the base script + voice timestamps + asset manifest. It is the **frame-accurate rendering instruction** consumed by the Remotion render engine.

### Transform Rules

1. **Merge timing:** Voice timestamps provide exact start/end per scene
2. **Resolve assets:** Map asset manifest URLs to layers
3. **Apply template:** Load template rules (e.g., `hybrid-kinetic`) for transitions, cuts/min, grade
4. **Generate layers:** Per scene — video/image layer, subtitle layer, kinetic text, overlays
5. **Caption sync:** Word-level timestamps from voice → word-by-word subtitle animation
6. **Transitions:** Apply between scenes per template rules
7. **Brand elements:** Inject intro, outro, watermark, subscribe banner per channel config
8. **Effects:** Color grade, film grain, vignette per template

### Transform Function (Python)

```python
def transform_remotion_view(
    script_base: dict,
    voice_result: dict,
    asset_manifest: dict,
    thumbnail_result: dict,
    channel_dna: dict,
    template: dict,
    brand_config: dict,
) -> dict:
    """
    Pure function: all inputs → Direction Format v3 JSON.
    This is the most complex transform — produces frame-accurate rendering instructions.
    """

    fps = 30
    segments = []
    current_ms = 0

    # Inject intro (if channel has one)
    if brand_config.get("intro_enabled"):
        segments.append(build_intro_segment(brand_config, fps, current_ms))
        current_ms += brand_config.get("intro_duration_ms", 3000)

    for scene in script_base["scenes"]:
        voice_scene = find_voice_scene(voice_result, scene["id"])
        asset_scene = find_asset_scene(asset_manifest, scene["id"])

        # Duration: from voice if available, else hint
        duration_ms = int((voice_scene["duration_s"] if voice_scene else scene["duration_hint_s"]) * 1000)

        # Build layers for this segment
        layers = []

        # Layer 1: Background video/image
        if asset_scene and asset_scene.get("clips"):
            clip = asset_scene["clips"][0]  # Primary clip
            layers.append({
                "type": "video",
                "src": clip["url"],
                "start_f": ms_to_frames(current_ms, fps),
                "end_f": ms_to_frames(current_ms + duration_ms, fps),
                "effects": [template.get("color_grade", "fx.grade.natural_cinematic")],
                "fit": "cover",
                "animation": select_animation(scene, template),
            })

        # Layer 2: Subtitles (word-by-word sync)
        if voice_scene and voice_scene.get("word_timestamps"):
            layers.append({
                "type": "subtitle",
                "style": template.get("caption_style", "bottom_center_subtitle"),
                "words": voice_scene["word_timestamps"],
                "highlight_words": scene.get("emphasis_words", []),
            })

        # Layer 3: Kinetic text (for emphasis words)
        if scene.get("emphasis_words") and not scene["visual_only"]:
            for word in scene["emphasis_words"][:2]:
                layers.append({
                    "type": "kinetic_text",
                    "text": word.upper(),
                    "preset": "scene.kinetic.scale_punch",
                    "position": "center",
                    "start_f": ms_to_frames(current_ms + duration_ms // 3, fps),
                    "end_f": ms_to_frames(current_ms + duration_ms // 3 + 1000, fps),
                })

        # Determine transition
        transition = select_transition(scene, template)

        segments.append({
            "id": scene["id"],
            "start_ms": current_ms,
            "duration_ms": duration_ms,
            "scene_preset": map_scene_preset(scene, template),
            "scene_overrides": {},
            "layers": layers,
            "transition_out": transition,
            "audio": {
                "narration": voice_scene["audio_url"] if voice_scene else None,
                "music_volume": 0.15 if not scene["visual_only"] else 0.4,
                "sfx": find_sfx(asset_manifest, scene["id"]),
            },
        })

        current_ms += duration_ms

    # Inject outro
    if brand_config.get("outro_enabled"):
        segments.append(build_outro_segment(brand_config, fps, current_ms))
        current_ms += brand_config.get("outro_duration_ms", 5000)

    return {
        "version": "3.0",
        "meta": {
            "video_id": script_base["script_id"],
            "channel_id": script_base["channel_id"],
            "title": script_base["title"],
            "duration_target_seconds": current_ms / 1000,
            "aspect": "16:9" if script_base["content_mode"] == "long_form" else "9:16",
            "fps": fps,
            "resolution": {"width": 1920, "height": 1080} if script_base["content_mode"] == "long_form" else {"width": 1080, "height": 1920},
        },
        "template": template["name"],
        "theme": {
            "primary_color": brand_config["primary_color"],
            "accent_color": brand_config["accent_color"],
            "background_color": brand_config.get("background_color", "#000"),
            "text_color": brand_config.get("text_color", "#FFF"),
            "fonts": brand_config.get("fonts", {"heading": "Inter", "body": "Inter"}),
        },
        "grade_preset": template.get("color_grade", "fx.grade.natural_cinematic"),
        "global_overlays": [
            {"type": "vignette", "intensity": 0.3},
            {"type": "film_grain", "preset": "fx.grain.35mm", "intensity": 0.15},
        ],
        "audio_master": {
            "music_url": asset_manifest.get("music", {}).get("url"),
            "music_volume": 0.15,
            "ducking": True,
            "ducking_threshold": -20,
        },
        "segments": segments,
    }
```

### Output Schema (Direction Format v3)

```json
{
  "version": "3.0",
  "meta": {
    "video_id": "VID_BS001_20250425_001",
    "channel_id": "BS001",
    "title": "4 Types of Shivers Your Body Produces (And What Each Means)",
    "duration_target_seconds": 480,
    "aspect": "16:9",
    "fps": 30,
    "resolution": { "width": 1920, "height": 1080 }
  },
  "template": "hybrid-kinetic",
  "theme": {
    "primary_color": "#FF3B30",
    "accent_color": "#FFD60A",
    "background_color": "#000",
    "text_color": "#FFF",
    "fonts": { "heading": "Inter", "body": "Inter" }
  },
  "grade_preset": "fx.grade.cinematic_teal_orange",
  "global_overlays": [
    { "type": "vignette", "intensity": 0.3 },
    { "type": "film_grain", "preset": "fx.grain.35mm", "intensity": 0.15 }
  ],
  "audio_master": {
    "music_url": "s3://yt-automation/assets/.../music.mp3",
    "music_volume": 0.15,
    "ducking": true,
    "ducking_threshold": -20
  },
  "segments": [
    {
      "id": "s1",
      "start_ms": 0,
      "duration_ms": 15000,
      "scene_preset": "scene.stock_footage",
      "scene_overrides": {},
      "layers": [
        {
          "type": "video",
          "src": "s3://yt-automation/assets/.../stock_001.mp4",
          "start_f": 0,
          "end_f": 450,
          "effects": ["fx.grade.cinematic_teal_orange"],
          "fit": "cover",
          "animation": "anim.ken_burns.slow_zoom_in"
        },
        {
          "type": "subtitle",
          "style": "word_highlight_animated",
          "words": [
            { "word": "Right", "start_ms": 200, "end_ms": 400 },
            { "word": "now", "start_ms": 400, "end_ms": 550 },
            { "word": "your", "start_ms": 600, "end_ms": 750 },
            { "word": "muscles", "start_ms": 800, "end_ms": 1100, "highlight": true }
          ],
          "highlight_words": ["muscles", "twenty times", "heat"]
        },
        {
          "type": "kinetic_text",
          "text": "MUSCLES",
          "preset": "scene.kinetic.scale_punch",
          "position": "center",
          "start_f": 150,
          "end_f": 180
        }
      ],
      "transition_out": { "type": "trans.dissolve.slow", "duration_f": 15 },
      "audio": {
        "narration": "s3://yt-automation/audio/.../scene_s1.mp3",
        "music_volume": 0.15,
        "sfx": []
      }
    },
    {
      "id": "s3",
      "start_ms": 27000,
      "duration_ms": 3000,
      "scene_preset": "scene.stock_footage",
      "scene_overrides": {},
      "layers": [
        {
          "type": "video",
          "src": "s3://yt-automation/assets/.../stock_mountain.mp4",
          "start_f": 810,
          "end_f": 900,
          "effects": ["fx.grade.cinematic_teal_orange"],
          "fit": "cover",
          "animation": "anim.ken_burns.slow_pan_right"
        }
      ],
      "transition_out": { "type": "trans.cut" },
      "audio": {
        "narration": null,
        "music_volume": 0.4,
        "sfx": []
      }
    }
  ]
}
```

### Template Reference

Templates define rendering rules. They are stored in the Remotion repo at `src/registry/`.

| Template            | Stock Footage | Kinetic Text | Data Viz | Cuts/min | Grade              |      Caption Style       |
| ------------------- | :-----------: | :----------: | :------: | :------: | ------------------ | :----------------------: |
| `hybrid-kinetic`    |    35-50%     |    25-35%    |  10-15%  |   8-14   | mood_responsive    | word_highlight_animated  |
| `stock-documentary` |    55-70%     |    15-25%    |  5-15%   |   6-8    | natural_cinematic  |  bottom_center_subtitle  |
| `2d-animated`       |      0%       |    25-35%    |  20-30%  |   8-12   | bright_flat_design | integrated_animated_text |
| `data-heavy`        |    20-30%     |    15-20%    |  30-45%  |   6-10   | clean_corporate    |  bottom_center_subtitle  |

### Quality Gates (Remotion View)

| Gate                          | Threshold                | Action on Fail         |
| ----------------------------- | ------------------------ | ---------------------- |
| Direction coherence           | ≥ 8.5                    | Regenerate v3          |
| v3 schema valid               | Pass Zod validation      | Regenerate             |
| Timeline continuity           | No gaps between segments | Fix gaps               |
| All asset URLs exist          | 100%                     | Use fallback assets    |
| Caption timing matches audio  | ±200ms per word          | Recalculate            |
| Template rules respected      | All ratios within range  | Adjust layers          |
| Total duration ±10% of target | Within range             | Trim/extend            |
| Cross-channel similarity      | <40%                     | Modify template/assets |

---

## Short-Form (Shorts) Adaptations

For `content_mode: "short_form"`:

| Aspect       | Long-form          | Short-form                |
| ------------ | ------------------ | ------------------------- |
| Duration     | ~480s (8 min)      | ~45s                      |
| Word count   | ~1100              | ~80                       |
| Aspect ratio | 16:9               | 9:16                      |
| Resolution   | 1920×1080          | 1080×1920                 |
| Scenes       | 15-25              | 3-5                       |
| Thumbnail    | Yes (DALL-E)       | No (auto-generated frame) |
| Outro        | Full endscreen     | Quick subscribe CTA       |
| Captions     | Word-highlight     | Full-screen animated      |
| Music        | Ambient underscore | Beat-driven, louder       |

The same three views apply, with shorter scenes and simplified structure.

---

## Determinism & Caching

All transforms are **deterministic pure functions**:

- Same `script_base` + same `voice_config` → same `script_voice.json`
- Same `script_base` + same `voice_result` → same `script_assets.json`
- Same inputs → same `script_remotion.json`

**Cache keys:**

```
voice_view:   sha256(script_base.scenes[narrated] + voice_config)
assets_view:  sha256(script_base.scenes + voice_result.timing)
remotion_view: sha256(script_base + voice_result + asset_manifest + template + brand_config)
```

All three views are stored in MinIO alongside the base script:

```
s3://yt-automation/scripts/{channel_id}/{video_id}/
├── script_base.json
├── script_voice.json
├── script_assets.json
└── script_remotion.json
```

---

## Data Flow Summary

```
Script Service
  │
  ├─ Produces: script_base.json  ──────────────────────────┐
  │                                                         │
  ├─ transform_voice_view()  → script_voice.json            │
  │      │                                                  │
  │      └─ Voice Service → voice_result (audio + timing)   │
  │                              │                          │
  ├─ transform_assets_view() → script_assets.json           │
  │      │                       (uses voice timing)        │
  │      └─ Assets Service → asset_manifest                 │
  │                              │                          │
  └─ Thumbnail Service → thumbnail_result                   │
                              │                             │
                              ▼                             │
                    Assembly Service                         │
                    transform_remotion_view()  ◄─────────────┘
                              │
                              ▼
                    script_remotion.json (v3)
                              │
                              ▼
                    Remotion Render Service
                              │
                              ▼
                    Final MP4 / Short
```
