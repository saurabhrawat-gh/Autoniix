# Budget Estimator (Premium Providers, No Quality Compromise)

Scope: 10 channels producing long- and short-form videos using premium providers only (LLM: GPT‑4o/Claude/Gemini family, TTS: FishAudio PAYG, Thumbnails: DALL·E 3, Assets: Envato + free stock). Estimates include infrastructure and subscriptions. Use this as a planning baseline; actuals should be validated with usage logs.

---

## Provider mix assumed (premium‑only)
- LLM (bulk): GPT‑4o‑mini or Claude Haiku or Gemini 1.5 Flash
- LLM (critical steps): GPT‑4o or Claude Sonnet (final long‑form polish, complex direction JSON)
- Thumbnails: DALL·E 3 (with GPT‑4o Vision QC, max 1 retry)
- TTS: FishAudio PAYG (all content)
- Embeddings: OpenAI text‑embedding‑3‑small (negligible cost)
- Stock assets: Envato primary; Pixabay/Pexels fallback (free)

---

## Cost assumptions (conservative/typical ranges)
- Infrastructure (single VM running full stack): $60–$120 / month (typical: $80)
- Envato Elements subscription: $16–$33 / month (typical: $33)
- TTS (FishAudio): $15 per 1,000,000 UTF‑8 bytes. Approx 1 minute ≈ 1,100 bytes ⇒ ~$0.0165/min
- Thumbnails (DALL·E 3): $0.06–$0.16 per image attempt; target 1.2 images/video on average (concept QC + 1 retry max)
- LLM per video (aggregated, with token caps & limited retries):
  - Long (8–10 min): $0.90–$1.80 (typical: $1.20)
  - Short (1 min): $0.25–$0.50 (typical: $0.35)

Notes:
- The LLM per‑video estimates already include research, draft, critique, QC/compliance/humanization, and direction JSON with premium escalation for critical steps (polish/direction) and bounded retries.
- If your provider region/pricing differs, adjust the per‑video figures or use the formulae below.

---

## Formulas
- Minutes per month = 9 × (# long) + 1 × (# short)
- TTS $ = Minutes × 0.0165
- Thumbnail images = 1.2 × (total videos)
- Thumbnail $ = Thumbnail images × $0.10 (use $0.06 low, $0.16 high)
- LLM $ = (# long × Long_LLM_$) + (# short × Short_LLM_$)
- Fixed $ = Infra ($80 typical) + Envato ($33)
- Total $ = TTS $ + Thumbnail $ + LLM $ + Fixed $

---

## Scenarios (typical case)
Using: Long_LLM_$ = $1.20, Short_LLM_$ = $0.35, Thumbnail attempt = $0.10, Attempts/video = 1.2, Infra=$80, Envato=$33.

| # | Scenario | Long | Short | Minutes | TTS $ | Thumb imgs | Thumb $ | LLM $ | Fixed $ | Total $ |
|---|----------|-----:|------:|--------:|------:|-----------:|--------:|------:|--------:|--------:|
| 1 | 10 ch: 40 long + 200 shorts | 40 | 200 | 560 | 9.24 | 288 | 28.80 | 118.00 | 113 | 269.04 |
| 2 | 10 ch: 40 long + 280 shorts | 40 | 280 | 640 | 10.56 | 384 | 38.40 | 146.00 | 113 | 307.96 |
| 3 | 10 ch: 80 long + 120 shorts | 80 | 120 | 840 | 13.86 | 240 | 24.00 | 138.00 | 113 | 288.86 |
| 4 | 8 ch: 32 long + 160 shorts  | 32 | 160 | 448 | 7.39 | 230 | 23.04 | 94.40  | 113 | 237.83 |
| 5 | 8 ch: 32 long + 224 shorts  | 32 | 224 | 512 | 8.45 | 307 | 30.72 | 116.80 | 113 | 269.0  |
| 6 | 10 ch: 64 long + 96 shorts  | 64 | 96  | 672 | 11.09 | 192 | 19.20 | 110.40 | 113 | 253.69 |

Interpretation (typical case):
- Fits comfortably: #1, #4, #5, #6
- Borderline: #2 (slightly > $300 unless we shave attempts/tokens)
- Fits (typical) but tight at high‑end usage: #3

---

## Low / High sensitivity (how it can vary)
- Low case (cheaper): Long LLM $0.90, Short LLM $0.25, Thumbs $0.06/attempt → scenario #2 total ≈ $252.6 (fits)
- High case (heavier usage): Long LLM $1.80, Short LLM $0.50, Thumbs $0.16/attempt → scenario #2 total ≈ $397 (over)

Conclusion: with token caps, bounded retries, and average 1.2 thumbnail attempts/video, scenario #2 can be kept at/under $300; otherwise it can exceed.

---

## Guardrails to stay in budget without quality loss
- LLM
  - Bulk tasks on GPT‑4o‑mini/Haiku/Flash; premium (GPT‑4o/Sonnet) only for final long‑form polish and direction JSON when gates demand it.
  - Cap rewrites: Longs ≤2 loops; Shorts ≤1 loop.
  - Strict max tokens per phase; abort/repair on QC fail.
- Thumbnails (DALL·E 3)
  - Target ≤1.2 attempts/video: concept pre‑QC, vision‑QC once, then stop.
  - Reuse successful design presets/styles per channel where applicable.
- TTS (FishAudio)
  - Cost is negligible; no change needed.
- Assets (Envato)
  - Prefer shorter licensed clips, reuse B‑roll across shorts of same topic cluster where editorially sound.
- Concurrency
  - Scale `worker-production` and `remotion-worker` to avoid long queues; keep attempts bounded regardless of scale.

---

## Actionable recommendations
- Safest under $300 with headroom: Scenarios #1, #4, #5, #6.
- Scenario #2 (40 long + 280 shorts) works if:
  - Thumbnail attempts avg ≤1.1/video, AND
  - Long LLM avg ≤$1.10, Short LLM avg ≤$0.33 (achieved via caps and limited premium escalation).
- Scenario #3 works in typical case but can exceed $300 in high‑usage weeks; use stricter caps or accept occasional overage.

---

## How to validate with real data
- Enable per‑phase usage logging (LLM input/output tokens, image attempts, TTS minutes) — already integrated in services; roll up monthly in Analytics.
- Compare actuals to these estimates; adjust Long/Short LLM per‑video targets and thumbnail attempt target.
- If totals trend >$300, first reduce thumbnail retries; second, shift one non‑critical step (e.g., research QC) to budget model.

---

## Appendix: Recomputing for your prices
Replace the typicals with your own:
- Long_LLM_$, Short_LLM_$
- Thumbnail $/attempt and attempts/video
- Infra $, Envato $
Then recompute the table using the formulas above.
