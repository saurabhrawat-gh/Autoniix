# Channel Creation Guide

> **Reference**: Every field the system uses when you create a channel manually via the dashboard.
> Path: Dashboard → Channels → + Add Channel

---

## What is a Channel?

A channel is a fully independent YouTube content identity. Each channel has:
- Its own niche, audience, brand voice, visual style, and posting cadence
- Its own AI configuration (how scripts are written, how videos are edited)
- Its own provider assignments (which voice, which LLM, etc.)
- Its own content pipeline and performance tracking

One Autoniix instance can run **multiple channels in parallel**, each producing independently.

---

## Required Fields (Minimum to Create)

| Field | Example | What It Means |
|---|---|---|
| `channel_name` | `Body Signals - Sleep & Recovery` | Human-readable name shown in the dashboard |
| `channel_id` | `BS_SLEEP01` | Short unique ID used internally (no spaces; uppercase recommended) |
| `niche` | `health` | Broad topic category: `health`, `finance`, `psychology`, `tech`, `lifestyle` |
| `status` | `active` | Start as `active` to enable scheduling, or `disabled` to set up first |

---

## Full Field Reference

### Identity & Niche

| Field | Type | Description |
|---|---|---|
| `channel_id` | string | **Unique** short identifier. e.g. `BS_SLEEP01`. Used in video IDs, file paths. |
| `channel_name` | string | Display name. Shown in dashboard and used in video metadata generation context. |
| `niche` | string | Top-level topic. Used for AI research and competitor analysis scoping. |
| `sub_niche` | string | Specific angle within the niche. e.g. `sleep_recovery`, `gut_digestion`. |
| `belief_territory` | string | The *false belief your audience holds* that your channel challenges. e.g. `sleep_is_just_rest`. This is fed to the AI hook writer. |
| `intellectual_lens` | string | The analytical framework your channel uses. e.g. `sleep_neuroscience`, `behavioral_finance`. Guides research prompts. |
| `topic_domain` | string | Comma-separated list of topic keywords the AI should stay within. e.g. `sleep science, circadian rhythm, melatonin, REM cycles`. |

### Brand Voice & Narrative

| Field | Options / Type | Description |
|---|---|---|
| `brand_voice` | `calm_authoritative`, `warm_empathetic`, `scientific_curious`, `gentle_reassuring`, `sharp_insightful`, `energetic_motivating`, `clear_trustworthy`, `direct_empowering`, `wise_measured`, `sharp_provocative` | The *personality* of the narrator. Passed to script generation prompts. |
| `narrative_rhythm` | `revelation`, `transformation`, `discovery`, `comfort_to_clarity`, `myth_to_truth`, `step_by_step`, `wisdom_unfolding`, `myth_destruction` | The structural arc of your videos. |
| `emotional_contract` | `curiosity_to_understanding`, `hope_to_confidence`, `confusion_to_clarity`, `fear_to_calm`, `frustration_to_empowerment`, `ignorance_to_awareness`, `shame_to_control`, `naivety_to_awareness`, `chaos_to_calm` | What emotional journey the viewer goes through from start to finish. |
| `content_style` | `educational_narrative` *(currently only option)* | How content is structured. |

### Content Mode & Duration

| Field | Options | Description |
|---|---|---|
| `content_mode` | `short`, `long`, `both` | Whether this channel produces Shorts (60s), long-form (8-12min), or both. |
| `planned_duration` | integer (days) | How many days ahead the system plans content. Default: 45. |
| `target_word_count` | integer | Short-form target word count. Default: 80. |
| `max_script_words_long` | integer | Max words for long-form scripts. Default: 1200. |
| `min_script_words_long` | integer | Min words for long-form scripts. Default: 1000. |
| `max_script_words_short` | integer | Max words for short-form scripts. Default: 90. |
| `min_script_words_short` | integer | Min words for short-form scripts. Default: 70. |
| `words_per_video_long` | integer | Target word count per long-form video. Default: 1100. |
| `words_per_video_short` | integer | Target word count per short. Default: 80. |
| `videos_per_week_long` | integer | Long-form videos to produce per week. Default: 1. |
| `videos_per_week_short` | integer | Short-form videos to produce per week. Default: 7. |
| `long_form_duration` | integer (seconds) | Target duration for long videos. Default: 600 (10 min). |
| `short_form_duration` | integer (seconds) | Target duration for Shorts. Default: 60. |

### Format & Presentation

| Field | Options | Description |
|---|---|---|
| `primary_format_long` | `educational_explainer`, `listicle`, `case_study`, `debate`, `tutorial` | Long-form content format. |
| `primary_format_short` | `hook_fact_payoff`, `myth_bust`, `tip_reveal`, `storytime_flash` | Short-form content format. |

### Audience & CTA

| Field | Type | Description |
|---|---|---|
| `target_audience` | string | Who watches this channel. e.g. `25-45_health_curious`, `22-40_beginner_investors`. Used in script generation. |
| `cta_style_long` | `soft_subscribe_reminder`, `strong_cta`, `course_pitch`, `none` | Call-to-action style for long-form. |
| `cta_style_short` | `none`, `profile_visit`, `soft_subscribe_reminder` | CTA style for Shorts. |

### Hook Configuration

| Field | Type | Description |
|---|---|---|
| `hook_length_seconds_long` | integer | How many seconds the hook should be on long-form. Default: 8. |
| `hook_length_seconds_short` | integer | Hook length for Shorts. Default: 2. |

### Performance Targets

| Field | Type | Description |
|---|---|---|
| `retention_target_long` | decimal (0–1) | Target average view duration ratio for long-form. Default: 0.45 (45%). |
| `retention_target_short` | decimal (0–1) | Target retention for Shorts. Default: 0.85 (85%). |
| `target_ctr` | decimal | Target click-through rate. Default: 0.080 (8%). |
| `target_avd_percent` | decimal | Target average view duration as percentage. Default: 0.450. |

### Safety & Compliance

| Field | Type | Description |
|---|---|---|
| `forbidden_words` | string (comma-separated) | Words/phrases the AI must **never** use in scripts. Anything medically or legally dangerous. e.g. `cure, guaranteed, miracle, treat, diagnose, prescription`. |

### Thumbnail & Visual Identity

| Field | Type / Options | Description |
|---|---|---|
| `thumbnail_style` | string | Descriptor of the thumbnail aesthetic. e.g. `dark_blue_minimal`, `pink_warm_close`. |
| `primary_color` | hex string | Brand primary color. e.g. `#1A237E`. Used in thumbnail generation prompts. |
| `secondary_color` | hex string | Brand secondary color. e.g. `#E8EAF6`. |
| `max_thumbnail_words` | integer | Maximum word count on thumbnail. Default: 4. |
| `visual_only_ratio` | decimal (0–1) | What fraction of thumbnails should be visual-only (no text). Default: 0.12. |
| `font_family` | string | Font name for thumbnails. e.g. `Montserrat`, `Poppins`, `Oswald`. |

### Caption & Color

| Field | Options | Description |
|---|---|---|
| `caption_style` | `word_highlight`, `word_underline`, `word_glow`, `word_bold_pop`, `word_sharp_flash`, `word_fade_elegant` | How captions animate on screen. |
| `color_grade_preset` | string | Video color grade preset. e.g. `cool_clinical`, `warm_soft`, `dark_cinematic`. |

### Pacing & Templates

| Field | Options / Type | Description |
|---|---|---|
| `pacing_style` | `slow_calming`, `warm_steady`, `dynamic_curious`, `gentle_progressive`, `fast_energetic`, `measured_authoritative`, `sharp_provocative`, `direct_practical`, `fast_provocative`, `slow_philosophical` | Overall editing pace for this channel. |
| `intro_template` | string | Name of the intro template (from Remotion). e.g. `body_signals_intro`. |
| `outro_template` | string | Name of the outro template. e.g. `body_signals_outro`. |
| `video_template` | string | Overall Remotion video template. e.g. `body_signals_v1`. |

### Publishing Schedule

| Field | Options / Type | Description |
|---|---|---|
| `posting_frequency` | `daily`, `weekly`, `twice_weekly`, `custom` | How often new videos are posted. |
| `timezone` | IANA tz string | e.g. `Asia/Kolkata`, `America/New_York`. Used for scheduling uploads. |

### Voice Configuration

| Field | Type | Description |
|---|---|---|
| `elevenlabs_voice_id` | string | ElevenLabs voice ID from your account. e.g. `21m00Tcm4TlvDq8ikWAM` (Rachel). Leave blank if using Edge TTS or Fish Audio. |
| `voice_stability` | decimal (0–1) | ElevenLabs stability parameter. 0.5 = balanced. Higher = more consistent but less expressive. |
| `voice_similarity` | decimal (0–1) | ElevenLabs similarity boost. 0.75 = recommended default. |
| `voice_style` | decimal (0–1) | ElevenLabs style exaggeration. 0 = off, 0.4 = moderate expression. |

### Music & Audio

| Field | Options / Type | Description |
|---|---|---|
| `music_mood_default` | `ambient_calm`, `ambient_hopeful`, `ambient_curious`, `ambient_soothing`, `upbeat_motivating`, `corporate_light`, `ambient_thinking`, `motivational_drive`, `dark_suspense`, `ambient_philosophical` | Default background music mood for this channel. |
| `sfx_density` | `low`, `medium`, `high`, `minimal`, `none` | How many sound effects to use in editing. |

### Operations & Budget

| Field | Type | Description |
|---|---|---|
| `max_daily_api_spend` | decimal (USD) | Max $ this channel can spend on APIs per day. e.g. `5.00`. Hard stop. |
| `human_review_required` | `first_10`, `always`, `never`, `quality_gate` | When to require human approval before publishing. `first_10` = review first 10 videos. |
| `status` | `active`, `disabled`, `archived` | Channel operational status. Only `active` channels get scheduled. |

---

## Beliefs (Optional but Recommended)

After creating a channel, add 1–3 **beliefs** via the channel detail page.

A belief is a **false assumption your target audience holds** that your content challenges.

| Field | Example |
|---|---|
| `belief` | `sleep_is_just_rest` |
| `counter_narrative` | `Sleep is the most active brain state — it's when your body rebuilds` |
| `angle` | `sleep_neuroscience` |

These are fed directly into the research and hook generation AI prompts. More beliefs = richer topic diversity.

---

## Step-by-Step: Creating Your First Channel

1. Go to **Dashboard → Channels → + Add Channel**
2. Enter a **channel name** and auto-suggest a **channel ID** (e.g. `HEALTH01`)
3. Choose your **niche** (health / finance / psychology / tech / lifestyle)
4. Use the AI Assistant button to auto-generate a Brand DNA from just the channel name + niche
5. Review and adjust the generated fields — especially `forbidden_words`, `target_audience`, `posting_frequency`
6. Set `status = disabled` until you've added provider credentials and beliefs
7. Go to **Providers** → connect at minimum: an LLM, a TTS voice, and a stock footage provider
8. Return to the channel and set `status = active`
9. Trigger a test video from the dashboard to verify the full pipeline

---

## Channel ID Naming Convention

Use a prefix that identifies the brand + sub-niche:

```
<BRAND>_<SUBNICHE><INDEX>
```

Examples:
- `BS_SLEEP01` — Body Signals, Sleep niche, first channel
- `MD_INV01` — Money Decoded, Investing
- `MS_STOIC01` — Mind Shifts, Stoic
- `TECH_AI01` — Tech niche, AI sub-niche, first channel

Keep it uppercase, under 20 characters, no spaces.

---

## Common Mistakes

- **`forbidden_words` is empty** — Always add legally sensitive words for your niche (medical claims, financial guarantees, etc.)
- **`belief_territory` left generic** — This is the creative core of your channel. Be specific.
- **`elevenlabs_voice_id` set to placeholder** — Replace with a real voice ID from your ElevenLabs account, or switch to Fish Audio / Edge TTS in Providers
- **`posting_frequency = daily` but budget too low** — A daily Shorts channel uses ~$0.05–0.15/video in test mode. Set `max_daily_api_spend` accordingly.
- **Channel created without any providers** — The pipeline will fail immediately on first run if no LLM or TTS is connected.
