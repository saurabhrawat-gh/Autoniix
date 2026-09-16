# Asset Strategy: Premium-First, Netflix-Grade Quality

**Last Updated:** April 23, 2026
**Philosophy:** Premium quality is the default. Free sources supplement ONLY when they genuinely match or exceed premium quality.
**Quality Target:** Netflix documentary / Hollywood cinema / Apple keynote tier.

---

## The Core Principle

❌ **WRONG:** "Use free first, fallback to premium"
✅ **RIGHT:** "Use premium first. Free supplements only when it matches premium quality."

We pay $16.50/month for Envato specifically for premium quality. Defaulting to free defeats the purpose.

---

## Quality Benchmarks — Best of the Best

Every asset is scored against the BEST implementation across ALL of these:

### Editing Suites

- **Adobe Premiere Pro** — Industry-standard editing
- **Adobe After Effects** — Motion graphics king
- **DaVinci Resolve** — Color grading leader (film industry)
- **Final Cut Pro** — Apple polish
- **Avid Media Composer** — Hollywood editing

### Creator Tools

- **CapCut Pro** — Modern social/kinetic
- **Filmora** — Effects library leader
- **Apple Motion** — Keynote-grade motion

### Professional Plugins

- **Red Giant Universe** — Transitions, glitch, retro
- **Red Giant Magic Bullet Looks** — Cinematic grading
- **FilmConvert Nitrate** — Gold-standard film emulation
- **Boris FX Sapphire** — Broadcast-grade effects

### Reference Productions

- **Netflix docs:** Our Planet, The Last Dance, Formula 1: Drive to Survive
- **Apple keynotes:** Product reveal videos
- **YouTube elite:** Vox, ColdFusion, Kurzgesagt, Veritasium
- **Cinema:** Roger Deakins, Emmanuel Lubezki, Bradford Young grading

---

## Asset-by-Asset Decisions (Premium-First)

### 1. Film Grain

**Target:** Red Giant Universe "Retrograde" / Magic Bullet Looks — 95/100

| Source              | Quality   | Tier    | Role                                    |
| ------------------- | --------- | ------- | --------------------------------------- |
| **Envato Elements** | ⭐ 95/100 | Premium | ✅ **PRIMARY — default for all videos** |
| RocketStock Free    | 🟢 88/100 | Free    | 🔄 Supplement for extra variety         |

**Registry presets:** 70+ (50 Envato + 20 RocketStock)

### 2. SFX (Sound Effects)

**Target:** Boom Library / Krotos / Splice Sounds — 95/100

| Source              | Quality      | Tier    | Role                                      |
| ------------------- | ------------ | ------- | ----------------------------------------- |
| **Envato Elements** | ⭐ 92/100    | Premium | ✅ **PRIMARY — 700+ professional sounds** |
| Mixkit              | 🟢 85/100    | Free    | 🔄 Supplement for variety                 |
| Pixabay Audio       | 🟢 80/100    | Free    | 🔄 Supplement only                        |
| Freesound           | 🟡 70-85/100 | Free    | 🔄 Last resort (variable quality)         |

**Registry presets:** 1000+ (700 Envato + 300 curated free)

### 3. LUTs (Color Grading)

**Target:** DaVinci Resolve Film Emulation / Magic Bullet Looks — 95/100

| Source              | Quality   | Tier    | Role                                   |
| ------------------- | --------- | ------- | -------------------------------------- |
| **Envato Elements** | ⭐ 92/100 | Premium | ✅ **PRIMARY — 150+ cinematic LUTs**   |
| Lutify.me Free      | 🟢 90/100 | Free    | 🔄 Supplement (genuinely high quality) |
| RocketStock Free    | 🟢 88/100 | Free    | 🔄 Supplement (35 LUTs)                |

**Registry presets:** 215+ (150 Envato + 65 free)

### 4. Stock Footage

**Target:** Getty Images / Filmsupply — 95/100

| Source              | Quality   | Tier    | Role                                       |
| ------------------- | --------- | ------- | ------------------------------------------ |
| **Envato Elements** | ⭐ 92/100 | Premium | ✅ **PRIMARY — 5M+ 4K/6K clips**           |
| Pexels API          | 🟢 85/100 | Free    | 🔄 Supplement when keyword match is better |

### 5. Music

**Target:** Epidemic Sound / Musicbed / Artlist — 95/100

| Source                | Quality   | Tier    | Role                              |
| --------------------- | --------- | ------- | --------------------------------- |
| **Envato Elements**   | ⭐ 88/100 | Premium | ✅ **PRIMARY**                    |
| YouTube Audio Library | 🟢 80/100 | Free    | 🔄 Supplement for specific tracks |

### 6. Visual Overlays (Light Leaks, Dust, Bokeh)

**Target:** RocketStock Collider / ActionVFX — 95/100

| Source              | Quality   | Tier    | Role                         |
| ------------------- | --------- | ------- | ---------------------------- |
| **Envato Elements** | ⭐ 92/100 | Premium | ✅ **PRIMARY — Envato only** |

### 7. Motion Graphics Templates

**Target:** After Effects built-in / Motion Array — 92/100

| Source              | Quality   | Tier    | Role                           |
| ------------------- | --------- | ------- | ------------------------------ |
| **Envato Elements** | ⭐ 92/100 | Premium | ✅ **PRIMARY**                 |
| Custom Remotion     | ⭐ 95/100 | Code    | ✅ Build our own best-in-class |

### 8. Fonts

**Target:** Adobe Fonts / Monotype — 95/100

| Source              | Quality   | Tier    | Role                                                 |
| ------------------- | --------- | ------- | ---------------------------------------------------- |
| **Envato Elements** | ⭐ 93/100 | Premium | ✅ **PRIMARY — premium display fonts**               |
| Google Fonts        | 🟢 90/100 | Free    | 🔄 Supplement (Inter, Manrope — genuinely excellent) |

### 9. Icons

**Exception:** Free genuinely matches premium here.

| Source        | Quality   | Tier    | Role                                      |
| ------------- | --------- | ------- | ----------------------------------------- |
| **Lucide**    | ⭐ 95/100 | Free    | ✅ **PRIMARY (matches Apple SF Symbols)** |
| **Heroicons** | ⭐ 95/100 | Free    | ✅ **PRIMARY**                            |
| Envato Icons  | 🟢 85/100 | Premium | 🔄 Use for specific niche styles only     |

### 10. Illustrations

**Target:** Kurzgesagt / Duolingo / Slack design — 95/100

| Source              | Quality   | Tier    | Role                                             |
| ------------------- | --------- | ------- | ------------------------------------------------ |
| **Envato Elements** | ⭐ 92/100 | Premium | ✅ **PRIMARY — niche-specific (finance/health)** |
| Storyset            | 🟢 88/100 | Free    | 🔄 Supplement (animated variants)                |

---

## Premium-First Resolution Logic

```typescript
// src/services/assetResolver.ts
export class PremiumFirstResolver {
  selectBest(category: string, style?: string): Asset {
    // 1. Premium assets first (Envato)
    const premium = this.getAssets("premium", category, style);
    if (premium.length > 0) return this.highestQuality(premium);

    // 2. Only fallback to free if no premium match
    const free = this.getAssets("free", category, style);
    return this.highestQuality(free);
  }
}
```

---

## Asset Library Targets (Maximum Volume)

| Asset Type    | Envato (Primary) | Free (Supplement)  | Total     |
| ------------- | ---------------- | ------------------ | --------- |
| Film Grain    | 50 overlays      | 20 (RocketStock)   | **70+**   |
| SFX           | 700 sounds       | 300 (curated)      | **1000+** |
| LUTs          | 150 files        | 65 (free packs)    | **215+**  |
| Overlays      | 50 files         | 0                  | **50+**   |
| Music         | 80 tracks        | 20 (YT Library)    | **100+**  |
| Templates     | 100 templates    | 0                  | **100+**  |
| Fonts         | 20 premium       | 20 (Google)        | **40+**   |
| Icons         | 0                | 1300 (Lucide+Hero) | **1300+** |
| Illustrations | 70 niche         | 30 (Storyset)      | **100+**  |

**Grand Total: ~3,000+ premium-quality assets**

---

## Folder Structure

```
/public/assets/
├── grain/
│   ├── envato/                  # 50+ overlays (PRIMARY)
│   │   ├── 35mm_cinematic_fine/
│   │   ├── 16mm_documentary/
│   │   ├── 8mm_vintage/
│   │   ├── super8_warm/
│   │   └── damaged_archival/
│   └── rocketstock/             # 20 supplementary
│
├── sfx/
│   ├── envato/                  # 700+ PRIMARY
│   │   ├── whoosh/
│   │   ├── impact/
│   │   ├── ui/
│   │   ├── transition/
│   │   ├── ambient/
│   │   ├── cinematic/
│   │   └── foley/
│   └── free/                    # 300+ supplementary
│       ├── mixkit/
│       ├── pixabay/
│       └── freesound/
│
├── luts/
│   ├── envato/                  # 150+ PRIMARY
│   │   ├── cinematic/
│   │   ├── film_emulation/
│   │   ├── moody/
│   │   ├── documentary/
│   │   ├── commercial/
│   │   └── vintage/
│   ├── rocketstock/             # 35 supplementary
│   ├── lutify/                  # 10 supplementary
│   └── smallhd/                 # 20 supplementary
│
├── overlays/
│   └── envato/                  # 50+ Envato only
│       ├── light_leaks/
│       ├── dust/
│       ├── bokeh/
│       ├── lens_flares/
│       └── film_burns/
│
├── music/
│   ├── envato/                  # 80+ PRIMARY
│   └── youtube_library/         # 20+ supplementary
│
├── fonts/
│   ├── envato/                  # 20 premium display
│   └── google/                  # 20 workhorse
│
├── illustrations/
│   ├── envato/                  # 70+ niche-specific
│   └── storyset/                # 30+ animated
│
└── templates/
    └── envato/                  # 100+ motion graphics
```

---

## Video Output Quality Targets

### Stock Footage / B-Roll Videos

**Target:** Netflix documentary grade (_Our Planet_, _Drive to Survive_)

Every video MUST have:

- ✅ 4K+ stock footage (Envato primary)
- ✅ Professional 3D LUT grading (Envato LUTs)
- ✅ Real film grain overlay (Envato)
- ✅ Cinematic SFX on every transition (Envato)
- ✅ Emotional music bed (Envato)
- ✅ Light leak/dust overlays for organic feel (Envato)
- ✅ Professional lower thirds and titles
- ✅ 15+ Mbps bitrate, 1080p minimum

**Target Score:** ⭐ 95/100

### Animated Explainer Videos

**Target:** Kurzgesagt / Apple keynote grade

Every video MUST have:

- ✅ Premium illustrations (Envato)
- ✅ Smooth Apple Motion-grade animations
- ✅ Premium typography (Envato + Google)
- ✅ Cinematic LUT (subtle grading even on animation)
- ✅ Professional SFX on every action/transition
- ✅ High-quality music bed (Envato)

**Target Score:** ⭐ 95/100

---

## Quality Gates (Pre-Render Checklist)

Before any video renders, it must pass:

- [ ] All stock footage is 4K+ (Envato preferred)
- [ ] Color grading uses real 3D LUT (not CSS filter)
- [ ] Film grain is real footage overlay (not procedural SVG)
- [ ] Every transition has matching SFX
- [ ] Music is auto-ducked during voiceover
- [ ] Typography uses premium fonts
- [ ] Resolution: 1920×1080 minimum
- [ ] Bitrate: 15+ Mbps for YouTube upload
- [ ] LUFS loudness normalization applied

---

## Cost Summary

| Asset Source             | Cost             | Quality Contribution                |
| ------------------------ | ---------------- | ----------------------------------- |
| **Envato Elements Core** | **$16.50/month** | **85% of premium assets (PRIMARY)** |
| Free supplements         | $0               | 15% extra variety                   |
| **Total**                | **$16.50/month** | **Overall: ⭐ 92-95/100**           |

---

## Changelog

- **2026-04-23 (v2):** Rewrote to premium-first. Benchmarked against Premiere Pro, After Effects, DaVinci Resolve, Final Cut Pro, CapCut, Filmora, Red Giant, Magic Bullet, Boris FX. Target: Netflix-grade.
- **2026-04-23 (v1):** Initial (deprecated — was free-first)
