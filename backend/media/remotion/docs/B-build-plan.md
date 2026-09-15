# B. Phase-by-Phase Build Plan (targeting 100+ components / 400+ presets)

> Duration estimates assume 1 senior Remotion/React dev full-time. Double if part-time.

---

## Phase 0 — Foundations (Week 0, 3–5 days)

**Goal**: scaffolding before any feature work.

- Remotion project scaffold, TS strict, ESLint/Prettier
- `Root.tsx` with `MainVideo` (16:9) + `ShortFormVideo` (9:16) + `ThumbnailComp`
- **Preset registry pattern** (see doc C) — central `registry/` folder
- **Direction format JSON schema** (see doc D) with Zod validation
- `SceneRenderer` router (reads preset ID → resolves component + props)
- Express API skeleton: `/api/render`, `/api/render/:id`, `/api/thumbnail`, `/api/health`
- Render queue (BullMQ + Redis) — supports concurrent limit
- S3/R2 upload utility
- Dockerfile + docker-compose (app + redis)
- Callback webhook dispatcher (for n8n integration)
- CI: typecheck + lint + one smoke render

**Deliverable**: empty-but-valid JSON → 5-sec black video uploaded to S3, callback fired.

---

## Phase 1 — MVP Library (Weeks 1–2)

**Goal**: render ~70% of typical faceless YouTube videos.

### Scenes (6)

`StockFootageScene`, `KineticTypography` (w/ 4 anim presets), `FullScreenText`, `QuoteCard`, `ListAnimation`, `HookOpener`.

### Transitions (5 primitives → ~15 presets)

`Cut`, `Dissolve`, `Slide` (4 dirs), `Zoom`, `Flash`.

### Animations (6 primitives → ~15 presets)

`FadeIn`, `SlideIn`, `ScaleIn`, `Typewriter`, `BouncePop`, `CountUp`.

### Effects (4)

`ColorGrade` (5 LUTs), `Vignette`, `Grain`, `Letterbox`.

### Overlays (3)

`CaptionOverlay` (word-highlight + subtitle-bottom presets), `LowerThird` (2 presets), `Watermark`.

### Audio (4)

`AudioMixer`, `VoiceoverTrack`, `BackgroundMusic`, `DuckingEngine`.

### Templates (3)

`stock-documentary`, `hybrid-kinetic`, `listicle-top10`.

**Totals after Phase 1**: ~23 components, ~55 presets.
**Render target**: 10-min 1080p video on CX41 in 8–12 min.

---

## Phase 2 — Visual Enhancement (Weeks 3–5)

**Goal**: pro-channel parity. Charts, mockups, branding, Shorts.

### Scenes (+8 → 14 total)

`DataVisualization` (5 viz types), `SplitComparison`, `IconAnimation`, `CountdownScene`, `BeforeAfterSlider`, `SocialMockup`, `PhoneMockup`, `BrowserMockup`.

### Transitions (+6 primitives → ~35 total presets)

`Push`, `Cover`, `Wipe`, `Iris`, `BlurSwap`, `WhipPan`.

### Animations (+5 → ~30 total)

`BlurIn`, `FlipIn`, `ElasticIn`, `Pulse`, `WaveText`, `Shake`.

### Effects (+8 → 12 total)

`ChromaticAberration`, `Bloom`, `TiltShift`, `MotionBlur`, 10 more LUTs, `Duotone`, `FrameBorder`, `Glow`.

### Overlays (+6 → 9 total)

`ProgressBar`, `Particles` (3 presets: dust/snow/sparkles), `LogoBug`, `SubscribePing`, `EndCard`, `ChapterMarker`.

### Branding (3)

`IntroAnimation`, `OutroEndscreen`, `ChannelWatermark`.

### Audio (+2)

`SFXTrigger` w/ library of 50 SFX, `LoudnessNormalizer`.

### Templates (+7 → 10 total)

`2d-animated`, `data-heavy`, `product-review`, `tutorial-screencast`, `motivational-reel`, `cinematic-vlog`, `corporate-explainer`.

**Totals after Phase 2**: ~55 components, ~180 presets.

---

## Phase 3 — Premium (Weeks 6–9)

**Goal**: full feature set, advanced visuals.

### Scenes (+10 → 24 total)

`TimelineAnimation`, `ImageParallax`, `TextReveal`, `MapAnimation`, `MemeFrame`, `NewsTicker`, `CodeTyping`, `TerminalLog`, `WhiteboardDraw`, `Carousel`, `GridGallery`, `GaugeMeter`, `LeaderboardStats`, `VsBattleCard`.

### Transitions (+7 → 55+ presets)

`Morph`, `Glitch`, `Shatter`, `PageCurl`, `FilmBurn`, `LightLeak`, `Swirl`.

### Animations (+5 → 45+ presets)

`GlitchReveal`, `RollIn`, `Wobble`, char/word cascade variants, scramble text.

### Effects (+8 → 20 total)

`VHS`, `CRTScanlines`, `Halftone`, `LensDistortion`, `DustScratches`, `Mirror`, `Kaleidoscope`, LUT pack expansion.

### Overlays (+6 → 15 total)

`EmojiReactions`, `HashtagPopup`, `LikePing`, `CommentPing`, `SafeZoneGuides`, `NowPlaying`.

### Audio (+3)

`SFXLibrary` (expand to 150+), `BeatSyncMarker`, `CaptionAligner` (forced alignment).

### Templates (+6 → 16 total)

`podcast-clip`, `meme-explainer`, `news-breakdown`, `finance-chart-heavy`, `gaming-highlight`, `reaction-commentary`.

**Totals after Phase 3**: ~90 components, ~320 presets.

---

## Phase 4 — Specialty & Polish (Weeks 10–14)

**Goal**: niche scenes, 3D, final library expansion.

### Scenes (+11 → 35 total)

`PolaroidStack`, `DocumentReveal`, `ReactionCam`, `LyricVideo`, `PodcastWaveform`, `ProductShowcase3D` (R3F), `WeatherCard`.

### Templates (+5 → 21 total)

`educational-whiteboard`, `story-narrative`, `luxury-minimal`, `retro-vhs`, `cyberpunk-neon`.

### Infra hardening

- GPU acceleration via `@remotion/gpu` on supported VPS
- LUT asset CDN
- Preset preview thumbnail generator (auto-render 2-sec gifs of each preset)
- Preset picker UI (optional Admin panel)
- Performance budget guardrails (reject compositions exceeding CPU/mem targets)

**Totals after Phase 4**: ~121 components, ~400+ presets. Matches InVideo/Pictory tier.

---

## Phase 5 — CapCut-class Expansion (ongoing, months 4–12)

- Scale presets from 400 → 1000+ via variant generation
- Community preset marketplace format (JSON-only, no new components needed)
- Custom LUT upload
- User-authored template JSONs
- Lottie marketplace integration (thousands of icon animations for free)
- Rive file support for interactive-style animations

---

## Dependency Graph (critical path)

```
Phase 0 (foundation)
   ↓
Phase 1 MVP ──→ First production videos
   ↓
Phase 2 (parallel tracks possible: scenes ∥ effects ∥ templates)
   ↓
Phase 3 (same)
   ↓
Phase 4 specialty
```

Branding + Audio + Overlays can be worked in parallel by a second dev from Phase 2 onwards.

---

## Effort summary

| Phase | Weeks   | Components added | Preset total | Parity             |
| ----- | ------- | ---------------- | ------------ | ------------------ |
| 0     | 0.5–1   | 0 (scaffold)     | 0            | —                  |
| 1     | 2       | 23               | 55           | Faceless YT basics |
| 2     | 3       | +32 (55)         | 180          | Pro channel        |
| 3     | 4       | +35 (90)         | 320          | InVideo-ish        |
| 4     | 4       | +31 (121)        | 400+         | Pictory-tier       |
| 5     | ongoing | presets only     | 1000+        | CapCut-adjacent    |

**Realistic cost**: 10–14 weeks solo for Phases 0–4. 6–8 weeks with two devs.

---

## Risk Register

- **Render perf** — WebGL effects on CPU-only VPS are slow. Plan: GPU box (Hetzner GEX44) or effect budget per composition.
- **Asset storage** — LUTs + SFX + stock placeholders balloon disk. Plan: CDN + lazy load.
- **Font licensing** — Google Fonts safe; premium fonts need per-channel license tracking.
- **Stock licensing** — delegate to pipeline upstream; renderer only consumes URLs.
- **Preset sprawl** — without discipline presets become untested. Plan: auto-snapshot renders per preset in CI.
