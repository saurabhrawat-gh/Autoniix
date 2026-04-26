# Roadmap to 97/100 — Netflix-Grade Video Quality

**Start:** 🔴 51/100 (April 2026)
**Target:** ⭐ 97/100 (Netflix documentary / Apple keynote / Hollywood cinema grade)
**Asset Strategy:** Premium-first (Envato Core $16.50/month)

---

## Current State (Baseline)

| Category | Score |
|---|---|
| Overall | 🔴 51/100 |
| Color Grading | 🔴 35/100 (CSS filter tints — no real LUTs) |
| Film Look | 🔴 20/100 (no grain, looks digital) |
| Effects | 🔴 38/100 (basic procedural shaders) |
| Audio | 🔴 48/100 (100 SFX, no ducking) |
| Transitions | 🟡 55/100 (no motion blur, basic easing) |
| Scenes | 🟡 62/100 (basic layouts) |
| Animations | 🟢 72/100 (decent but limited easing) |
| Overlays | 🟢 75/100 (captions work, limited styles) |

---

## Phase 4: Premium Asset Foundations (51 → 78/100)

**Duration:** 2 weeks
**Cost:** $16.50 (Envato Core subscription)
**Impact:** Biggest single jump (+27 points)

### 4.1 — Premium Asset Integration (HIGHEST PRIORITY)
- [ ] Subscribe to Envato Elements Core
- [ ] Download 50+ film grain overlays (4K, real film scans)
- [ ] Download 700+ SFX (whoosh, impact, UI, transition, ambient, cinematic)
- [ ] Download 150+ LUTs (.cube files)
- [ ] Download 50+ visual overlays (light leaks, dust, bokeh, lens flares)
- [ ] Download 80+ music tracks
- [ ] Download 20+ premium fonts
- [ ] Organize into `/public/assets/` folder structure per ASSET-STRATEGY.md
- [ ] Also download free supplements (RocketStock grain/LUTs, Lutify, SmallHD)

**Files created:**
- `public/assets/grain/envato/` (50+ files)
- `public/assets/sfx/envato/` (700+ files)
- `public/assets/luts/envato/` (150+ .cube files)
- `public/assets/overlays/envato/` (50+ files)
- `public/assets/grain/rocketstock/` (20 supplement files)
- `public/assets/luts/rocketstock/` (35 supplement files)
- `public/assets/luts/lutify/` (10 supplement files)

### 4.2 — WebGL 3D LUT Color Grading System
- [ ] Build `src/components/effects/LUTGrade.tsx` — WebGL shader for 3D LUT application
- [ ] Implement .cube file parser (supports 17³, 33³, 65³ LUT sizes)
- [ ] Trilinear interpolation in fragment shader
- [ ] Build `src/registry/lutLibrary.ts` — 215+ LUT presets (150 Envato + 65 free)
- [ ] Register all LUTs in `src/registry/effects.ts`
- [ ] Replace CSS filter-based `ColorGrade.tsx` as default grading
- [ ] Add intensity/strength slider (0-100%)

**Impact:** Color Grading 35 → 92 (+57 pts)

### 4.3 — Real Film Grain Overlay System
- [ ] Build `src/components/effects/FilmGrainOverlay.tsx` — video texture overlay
- [ ] Uses `<OffthreadVideo>` for looping grain footage with blend modes
- [ ] Supports blend modes: overlay, soft-light, screen, multiply
- [ ] Build `src/registry/grainLibrary.ts` — 70+ grain presets
- [ ] Intensity, scale, blend mode, tint controls
- [ ] Register grain presets in `src/registry/effects.ts`
- [ ] Replace procedural SVG `Grain.tsx` as default grain

**Impact:** Film Look 20 → 90 (+70 pts)

### 4.4 — SFX Library Expansion (1000+ sounds)
- [ ] Expand `src/registry/sfxLibrary.ts` to 1000+ entries
- [ ] 700 Envato entries (PRIMARY) + 300 curated free entries
- [ ] 15+ categories with sub-categories
- [ ] Per-SFX quality rating (1-5 stars)
- [ ] Premium-first resolution logic in resolver
- [ ] Auto-SFX trigger system on transitions (configurable)

**Impact:** Audio SFX 65 → 88 (+23 pts)

### 4.5 — Premium-First Asset Resolver
- [ ] Build `src/services/assetResolver.ts` — unified premium-first resolution
- [ ] Premium assets checked first (Envato)
- [ ] Free supplements as fallback only
- [ ] Quality scoring per asset
- [ ] Category-based lookup (grain, sfx, lut, overlay)

### 4.6 — Visual Overlay Library
- [ ] Build `src/registry/overlayLibrary.ts` — light leaks, dust, bokeh presets
- [ ] Build `src/components/effects/VideoOverlay.tsx` — generic video overlay component
- [ ] 50+ overlay presets (all Envato)

**Phase 4 Result:** 🔴 51 → 🟢 **78/100** (+27 pts)

---

## Phase 5: Shader Effects Upgrade (78 → 89/100)

**Duration:** 2 weeks
**Benchmark:** Red Giant Universe / Boris FX Sapphire level

### 5.1 — Professional Shader Effects
- [ ] VHS upgrade: real footage overlay + per-scanline chromatic aberration + tracking error + head-switching + date HUD
- [ ] CRT upgrade: Brown-Conrady barrel + RGB phosphor triad + bloom + interlacing
- [ ] Glitch upgrade: per-scanline RGB displacement + block corruption + datamosh + pixel sorting
- [ ] Scanlines upgrade: WebGL shader with per-line variation + flicker + interlacing
- [ ] Light Leaks upgrade: real footage overlays from Envato (replacing procedural)

**Impact:** Effects 38 → 92 (+54 pts)

### 5.2 — Premium Transitions
- [ ] Zoom Punch: chromatic aberration + radial blur + camera shake + motion blur streaks
- [ ] Glitch Cut: per-scanline RGB + block corruption + audio glitch sync
- [ ] Shatter: pseudo-3D depth + 10 shard patterns + gravity physics
- [ ] Morph: SVG shape morphing + LAB color interpolation + displacement maps
- [ ] Add motion blur to ALL existing transitions
- [ ] Add 15+ easing curves (spring, elastic, bounce, overshoot)

**Impact:** Transitions 55 → 90 (+35 pts)

### 5.3 — Advanced Animations
- [ ] Add motion blur to all slide/scale animations
- [ ] 15+ easing curves across all animation presets
- [ ] Overshoot + settle for punch animations
- [ ] Stagger delay for grouped elements
- [ ] Optional 3D rotation during entry/exit

**Impact:** Animations 72 → 92 (+20 pts)

**Phase 5 Result:** 🟢 78 → 🟢 **89/100** (+11 pts)

---

## Phase 6: Scenes & Overlays Premium Upgrade (89 → 93/100)

**Duration:** 2 weeks

### 6.1 — Data Visualization Scenes
- [ ] Timeline: curved/bezier variants, 20+ marker styles, camera pan, parallax
- [ ] Map: animated routes with trim paths, 20+ markers, camera pan/zoom, multiple base maps
- [ ] Flowchart: 20+ node shapes, bezier connectors, auto-layout, animated data flow

### 6.2 — Code & Explainer Scenes
- [ ] Code typing: 20+ language syntax, animated cursor + blink, bracket matching, multi-file tabs
- [ ] Infographic scenes: animated charts (bar, line, pie, donut, gauge)
- [ ] Split-screen: animated divider, per-side LUT grading, dynamic ratio

### 6.3 — Captions & Text Animations
- [ ] Karaoke captions: 30+ styles matching CapCut, emoji support, word-bounce, gradient text
- [ ] Typewriter: cursor blink, per-character speed, SFX sync, backspace animation
- [ ] 30+ new text entrance animations (matching AE library)

**Impact:** Scenes 62 → 93, Overlays 75 → 93

**Phase 6 Result:** 🟢 89 → ⭐ **93/100** (+4 pts)

---

## Phase 7: Titles & Lower Thirds (93 → 94/100)

**Duration:** 1 week

### 7.1 — Premium Lower Thirds
- [ ] 30+ lower third template variants (news, corporate, creative, minimal)
- [ ] 20+ entrance + 20+ exit animations each
- [ ] Gradient/shadow/glow/outline/frosted-glass styling
- [ ] Logo/icon integration with auto-sizing
- [ ] Auto-width based on text content

### 7.2 — Title Cards
- [ ] 30+ title card templates (matching Apple keynote + Netflix quality)
- [ ] Kinetic typography (word-by-word, character-by-character)
- [ ] Text-as-mask with video fill
- [ ] Variable font weight animation

**Phase 7 Result:** ⭐ 93 → ⭐ **94/100** (+1 pt)

---

## Phase 8: Audio Mastery (94 → 96/100)

**Duration:** 2 weeks

### 8.1 — Smart Music System
- [ ] Auto-ducking (lower music during voiceover, configurable threshold/attack/release)
- [ ] Beat detection for transition sync (BPM analysis via Web Audio API)
- [ ] Crossfade between music tracks
- [ ] LUFS loudness normalization (-14 LUFS YouTube standard)
- [ ] Per-track EQ/compression

### 8.2 — Audio Polish
- [ ] Voiceover EQ/compression (De-ess, bass boost)
- [ ] SFX LUFS normalization across entire library
- [ ] Ambient bed auto-generation (subtle room tone)
- [ ] Stereo widening on music
- [ ] Audio fade-in/fade-out on all tracks

**Phase 8 Result:** ⭐ 94 → ⭐ **96/100** (+2 pts)

---

## Phase 9: Cinematic Polish (96 → 97/100)

**Duration:** 2 weeks

### 9.1 — Color Science
- [ ] Color space management (sRGB / Rec.709)
- [ ] Skin tone protection hue range
- [ ] Highlight/shadow split toning
- [ ] Vignette with custom shapes (elliptical, rectangular)
- [ ] Lift/gamma/gain controls

### 9.2 — Film Emulation
- [ ] FilmConvert-style emulation (Kodak 2383, Fuji 3510, Ilford HP5)
- [ ] Halation effect (red glow around highlights)
- [ ] Gate weave (subtle frame shake)
- [ ] Lens breathing simulation

### 9.3 — Advanced Compositing
- [ ] Blend mode support per layer (screen, multiply, overlay, soft-light, etc.)
- [ ] Layer masking with feathering
- [ ] Track mattes (alpha, luma)
- [ ] Depth of field simulation

**Phase 9 Result:** ⭐ 96 → ⭐ **97/100** (+1 pt)

---

## Phase 10: Perfection (97 → 100/100)

**Duration:** Ongoing

- [ ] 4K rendering support (3840×2160)
- [ ] HDR rendering pipeline (Rec.2020 / PQ)
- [ ] Dolby Vision LUT integration
- [ ] Pixel-perfect QA audit on every preset
- [ ] A/B test against Netflix Originals frames
- [ ] Performance optimization (render time per frame)
- [ ] Automated quality scoring pipeline

**Target:** Indistinguishable from Hollywood production

---

## Timeline Summary

| Phase | Duration | Score | Focus |
|---|---|---|---|
| **Phase 4** | 2 weeks | 51 → 78 | Premium assets + LUTs + grain + SFX |
| **Phase 5** | 2 weeks | 78 → 89 | Shader effects + transitions + motion |
| **Phase 6** | 2 weeks | 89 → 93 | Scenes + captions + data viz |
| **Phase 7** | 1 week | 93 → 94 | Titles + lower thirds |
| **Phase 8** | 2 weeks | 94 → 96 | Audio mastering |
| **Phase 9** | 2 weeks | 96 → 97 | Cinematic polish |
| **Phase 10** | Ongoing | 97 → 100 | Perfection |

**Total to 97/100:** ~11 weeks
**Total to 100/100:** ~15 weeks

---

## Changelog

- **2026-04-23:** Initial roadmap created. Premium-first, benchmarked against Premiere Pro, AE, DaVinci Resolve, FCP, CapCut, Filmora, Red Giant, Magic Bullet, Boris FX. Target: Netflix-grade output.
