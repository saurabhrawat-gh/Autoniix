# Remotion Renderer Architecture

---

## Project Structure

```
remotion-renderer/
├── src/
│   ├── compositions/
│   │   ├── MainVideo.tsx          # 16:9 master composition
│   │   ├── ShortFormVideo.tsx     # 9:16 Shorts composition
│   │   └── ThumbnailComp.tsx      # Thumbnail renderer
│   │
│   ├── components/
│   │   ├── scenes/                # 13 scene components
│   │   │   ├── SceneRenderer.tsx       # Routes to correct component
│   │   │   ├── StockFootageScene.tsx   # Video playback + effects
│   │   │   ├── KineticTypography.tsx   # Animated text sequences
│   │   │   ├── DataVisualization.tsx   # Charts, graphs, stats
│   │   │   ├── SplitComparison.tsx     # Side-by-side
│   │   │   ├── TimelineAnimation.tsx   # Process/timeline
│   │   │   ├── QuoteCard.tsx           # Styled quotes
│   │   │   ├── IconAnimation.tsx       # Animated icons
│   │   │   ├── ImageParallax.tsx       # Multi-layer parallax
│   │   │   ├── ListAnimation.tsx       # Animated bullets
│   │   │   ├── TextReveal.tsx          # Char-by-char reveal
│   │   │   ├── FullScreenText.tsx      # Bold statement
│   │   │   └── MapAnimation.tsx        # Location highlight
│   │   │
│   │   ├── overlays/              # 5 overlays
│   │   │   ├── CaptionOverlay.tsx      # Word-by-word subtitles
│   │   │   ├── LowerThird.tsx          # Info bar
│   │   │   ├── ProgressBar.tsx         # Video progress
│   │   │   ├── ParticleOverlay.tsx     # Ambient particles
│   │   │   └── VignetteOverlay.tsx     # Edge darkening
│   │   │
│   │   ├── transitions/           # 8 transitions
│   │   │   ├── TransitionRouter.tsx
│   │   │   ├── CutTransition.tsx
│   │   │   ├── DissolveTransition.tsx
│   │   │   ├── SlideTransition.tsx
│   │   │   ├── ZoomPunch.tsx
│   │   │   ├── FlashTransition.tsx
│   │   │   ├── WipeTransition.tsx
│   │   │   └── MorphTransition.tsx
│   │   │
│   │   ├── animations/            # 9 animations
│   │   │   ├── KenBurns.tsx, ScaleIn.tsx, SlideIn.tsx, FadeIn.tsx
│   │   │   ├── TypeWriter.tsx, CountUp.tsx, BouncePop.tsx
│   │   │   ├── GlitchReveal.tsx, WaveText.tsx
│   │   │
│   │   ├── branding/              # 4 branding
│   │   │   ├── IntroAnimation.tsx, OutroEndscreen.tsx
│   │   │   ├── ChannelWatermark.tsx, SubscribeBanner.tsx
│   │   │
│   │   ├── audio/                 # 4 audio
│   │   │   ├── AudioMixer.tsx, VoiceoverTrack.tsx
│   │   │   ├── BackgroundMusic.tsx, SFXTrigger.tsx
│   │   │
│   │   └── effects/               # 5 effects
│   │       ├── ColorGrade.tsx, BlurEffect.tsx, GrainOverlay.tsx
│   │       ├── LetterboxEffect.tsx, SpeedRamp.tsx
│   │
│   ├── templates/                 # Direction format rules
│   │   ├── stock-documentary.json
│   │   ├── 2d-animated.json
│   │   ├── hybrid-kinetic.json
│   │   └── data-heavy.json
│   │
│   ├── api/
│   │   ├── server.ts              # Express server
│   │   ├── renderEndpoint.ts      # POST /api/render
│   │   ├── thumbnailEndpoint.ts   # POST /api/thumbnail
│   │   ├── healthEndpoint.ts      # GET /api/health
│   │   └── statusEndpoint.ts      # GET /api/render/:id
│   │
│   ├── utils/
│   │   ├── colorGrading.ts, easing.ts, layout.ts, timing.ts
│   │
│   └── Root.tsx
├── package.json
├── remotion.config.ts
└── Dockerfile
```

---

## API Endpoints

### POST /api/render
```json
// Request
{
  "composition": "MainVideo",       // or "ShortFormVideo"
  "inputProps": { /* v3 JSON */ },
  "codec": "h264",
  "outputFormat": "mp4",
  "quality": 80,
  "callbackUrl": "https://n8n.../webhook/remotion-render-complete"
}
// Response
{ "renderId": "render_abc123", "status": "rendering", "estimatedDuration": 180 }
```

### GET /api/render/:id
```json
{
  "renderId": "render_abc123",
  "status": "done",           // rendering | done | failed
  "progress": 1.0,
  "outputUrl": "https://storage.../render_abc123.mp4",
  "duration": 145,            // seconds to render
  "fileSize": 52428800
}
```

### POST /api/thumbnail
```json
// Request
{
  "composition": "ThumbnailComp",
  "inputProps": {
    "background_url": "https://dalle-bg.png",
    "title_text": "Why You Shiver",
    "title_style": { "font": "Montserrat", "weight": 900, "size": 120, "color": "#FFF" },
    "layout": "text_left_image_right",
    "accent_color": "#FF0000"
  },
  "format": "png",
  "width": 1280,
  "height": 720
}
// Response
{ "thumbnailUrl": "https://storage.../thumb.png" }
```

### GET /api/health
```json
{
  "status": "healthy",
  "activeRenders": 1,
  "maxConcurrent": 3,
  "memoryUsage": "2.1GB / 8GB",
  "diskSpace": "12GB free"
}
```

---

## Segment Types Reference

| Type | Component | Props |
|------|-----------|-------|
| stock_video | StockFootageScene | src, trim, fit, position, size |
| kinetic_typography | KineticTypography | text, words, animation_type, style, bg |
| data_visualization | DataVisualization | viz_type, value, label, colors |
| full_screen_text | FullScreenText | text, style, bg, animation |
| split_comparison | SplitComparison | left, right, divider |
| timeline_animation | TimelineAnimation | events[], connector, direction |
| quote_card | QuoteCard | quote, source, style, icon |
| list_animation | ListAnimation | items[], animation, bullets |
| icon_animation | IconAnimation | icon, label, animation, size |
| image_parallax | ImageParallax | layers[], depth, motion |
| text_reveal | TextReveal | text, speed, cursor |
| map_animation | MapAnimation | region, highlights, zoom |

---

## Direction Format Templates

### Stock Documentary
```json
{
  "stock_footage_ratio": "55-70%",
  "kinetic_typography_ratio": "15-25%",
  "data_visualization_ratio": "5-15%",
  "cuts_per_minute": "6-8",
  "color_grade": "natural_cinematic",
  "allowed_transitions": ["dissolve", "cut", "fade_to_black", "slide"],
  "forbidden": ["flash", "glitch", "zoom_transition"],
  "caption_style": "bottom_center_subtitle",
  "music_style": "ambient_underscore"
}
```

### 2D Animated
```json
{
  "stock_footage_ratio": "0%",
  "character_animation_ratio": "40-50%",
  "kinetic_typography_ratio": "25-35%",
  "cuts_per_minute": "8-12",
  "color_grade": "bright_flat_design",
  "allowed_transitions": ["slide", "morph", "wipe", "bounce"],
  "forbidden": ["dissolve", "fade_to_black"],
  "caption_style": "integrated_animated_text",
  "music_style": "upbeat_corporate"
}
```

### Hybrid Kinetic (most faceless channels)
```json
{
  "stock_footage_ratio": "35-50%",
  "kinetic_typography_ratio": "25-35%",
  "data_visualization_ratio": "10-15%",
  "cuts_per_minute": "8-14",
  "color_grade": "mood_responsive",
  "allowed_transitions": ["cut", "slide", "zoom_punch", "dissolve"],
  "caption_style": "word_highlight_animated",
  "music_style": "cinematic_with_beats"
}
```

---

## Build Phases

### Phase 1: Minimum Viable (Week 1)
MainVideo, SceneRenderer, StockFootageScene, CaptionOverlay, AudioMixer, KineticTypography (scale_punch + word_cascade), CutTransition, DissolveTransition, ColorGrade, API server, ThumbnailComp

→ Can render stock footage videos with captions, music, text emphasis. Covers ~70%.

### Phase 2: Visual Enhancement (Week 2)
DataVisualization, FullScreenText, QuoteCard, ListAnimation, SlideTransition, ZoomPunch, FlashTransition, KenBurns, IntroAnimation, OutroEndscreen, VignetteOverlay, ShortFormVideo

→ Professional videos with data viz, transitions, branding.

### Phase 3: Premium (Week 3-4)
SplitComparison, TimelineAnimation, IconAnimation, ImageParallax, TextReveal, ParticleOverlay, GrainOverlay, MorphTransition, WipeTransition, CountUp, WaveText, SubscribeBanner, ProgressBar

→ Full feature set.

---

## Server Costs

| VPS | Specs | $/mo | Concurrent | Render Time (10min) |
|-----|-------|------|-----------|-------------------|
| Hetzner CX31 | 4 vCPU, 8GB | $24 | 1 | 8-15 min |
| Hetzner CX41 | 8 vCPU, 16GB | $36 | 2 | 5-10 min |
| Hetzner CX51 | 16 vCPU, 32GB | $58 | 3-4 | 3-7 min |
