# Provider Keys Checklist

**What you need to provision before the video pipeline can actually run.**

Order: minimum spend → maximum spend. You can skip optional providers if a primary in the same category is configured.

---

## REQUIRED — pipeline cannot run without these

### 1. LLM (script + research + quality gate + direction)
**Pick at least one. Multiple = fallback chain.**

| Provider | Min spend | Why | Where to add |
|---|---|---|---|
| **OpenAI** (recommended primary) | $5 prepaid credit | Default model `gpt-4o-mini` for most stages | `/dashboard/providers/credentials` → OpenAI |
| Anthropic Claude | $5 prepaid | Better for script quality, used as fallback | Same UI |
| Google Gemini | Free tier (15 RPM) | Cheapest fallback | Same UI |

> **Pick OpenAI first.** Most prompts in the codebase target OpenAI's API shape.

### 2. Search / Research
| Provider | Spend | Why |
|---|---|---|
| **SerpAPI** | $50/mo plan or pay-per-search | Used by `research_activity` to gather web context for scripts |
| (alt) Brave Search API | $5/mo | Cheaper alternative if you swap the research provider |

### 3. Voice / TTS
**Pick one.**

| Provider | Min spend | Notes |
|---|---|---|
| **ElevenLabs** (recommended) | $5/mo Starter (30k chars) | Best voice quality. `ELEVENLABS_MODEL_ID` already set |
| Fish Audio | Pay-per-use, ~$0.001/char | Cheaper, quality varies |
| Edge TTS | Free | Microsoft, no key needed, but lowest quality |

### 4. YouTube OAuth (for delivery + analytics)
This is **not just an API key** — it's a Google Cloud project setup.

**Steps:**
1. Go to https://console.cloud.google.com — create new project (e.g., "Autoniix Video Pipeline")
2. Enable APIs: **YouTube Data API v3** + **YouTube Analytics API**
3. OAuth consent screen → External → add scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/yt-analytics.readonly`
4. Add yourself as a Test User (so you don't need verification yet)
5. Create OAuth 2.0 Client ID → Web application
   - Authorized redirect URI: `https://dash.autoniix.com/auth/youtube/callback`
6. Copy Client ID + Client Secret → paste into `/dashboard/providers/credentials` → YouTube
7. From the dashboard, "Connect Channel" → OAuth flow stores refresh token in DB

**Cost:** Free (within quota). YouTube upload quota is 6 uploads/day per project by default; can be raised by submitting the app for verification.

---

## RECOMMENDED — pipeline runs but quality drops without these

### 5. Stock Assets (B-roll, images)
**Pick at least one.**

| Provider | Spend | Why |
|---|---|---|
| **Pexels** (recommended) | Free | 200 req/hr, decent stock library |
| Pixabay | Free | 5000 req/hr, alt library |
| Envato Elements | $16.50/mo | Premium, large library |

### 6. Music
| Provider | Spend |
|---|---|
| **Freesound** | Free with account | Used by `music.py` for background music selection |

### 7. Image Generation (thumbnails)
The `thumbnail` service uses OpenAI's image API by default (covered by #1 above). If you want alternatives:

| Provider | Spend |
|---|---|
| OpenAI DALL-E 3 (HD) | ~$0.08/image | Default in code |
| Replicate (SDXL) | $0.0023/image | Cheaper alternative |
| Stability AI | $10/mo for 5000 generations | Alt |

---

## OPTIONAL — for specific features only

### 8. News API (trend research)
- Provider: **NewsAPI.org**, free tier 100 req/day
- Used by NichePulse trend tracking

### 9. Resend (transactional emails)
- Provider: **Resend.com**, 3000 emails/mo free
- Used for invite, password reset, ownership transfer emails
- Without it, emails silently fail (in-app links still work)

### 10. Sentry (error tracking)
- Provider: **Sentry.io**, free tier 5k errors/mo
- Used by Sentry Agent for auto-bug-filing
- Without it, errors aren't captured but app still runs

---

## Minimum viable spend to create your first video

| Category | Provider | Cost |
|---|---|---|
| LLM | OpenAI | $5 prepaid |
| Search | SerpAPI | $50 / mo (cheapest plan) OR pay-per-use trial |
| Voice | ElevenLabs Starter | $5 / mo |
| Stock | Pexels | $0 |
| Music | Freesound | $0 |
| YouTube | OAuth setup | $0 |
| **Total month-1** | | **~$60** |

After month 1, expect **~$0.50-$2.00 per video** in actual usage costs (mostly LLM tokens + voice character count + image gen).

---

## How to add credentials in the dashboard

1. Login at https://dash.autoniix.com
2. Top nav → **Providers** → **Credentials**
3. Click "Add credential" → pick provider → paste key → Save
4. Encrypted with `SECRETS_ENCRYPTION_KEY` and stored in `provider_credentials` table
5. Top nav → **Providers** → **Chains** → drag providers into Test and Production chain order
6. Click **"Test"** on the chain to verify each credential responds

---

## Verification: am I ready to create a video?

Run this checklist:
- [ ] At least one LLM credential saved + chain configured
- [ ] SerpAPI credential saved
- [ ] At least one TTS credential saved
- [ ] At least one stock asset credential saved
- [ ] Freesound credential saved
- [ ] YouTube OAuth completed (channel shows "Connected" in `/dashboard/channels`)
- [ ] Test chain returns green dots on all stages in `/dashboard/providers/health`

If all 7 are checked → you can run a production. If any is missing → that stage will fail.
