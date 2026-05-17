# Service: Delivery

## Purpose

Uploads rendered videos to YouTube via the Data API, sets metadata
(title, description, tags, schedule), uploads the public thumbnail, and
records the resulting `video_id` back on `videos`.

## Port / source

- Port `8007`, memory 256M
- `src/services/delivery/main.py`
- `seo_optimizer.py` — title, description, tags optimisation (length
  limits, keyword density, click-bait score, length to retention curve)

## OAuth scopes required

- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/yt-analytics.readonly` (for the
  `RetentionFetchWorkflow`)

`GOOGLE_OAUTH_REFRESH_TOKEN` is exchanged for an access token per request.

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /upload` | Resumable upload of rendered video + metadata + thumbnail |
| `POST /optimise-metadata` | SEO pass on title/desc/tags |
| `POST /schedule` | Set `publishAt` for a scheduled video |
| `GET  /quota` | Remaining YouTube quota for the day |

## Test-mode guard

In test mode the upload call is short-circuited — the service logs a fake
upload event and returns `{video_id: null, simulated: true}` so the
workflow can complete. See `require_production()` in `src/environment.py`.

## Quota budgeting

Uploads cost 1600 YouTube quota units each (10k/day default project quota
→ ~6 uploads/day per project). The service refuses to enqueue if
remaining quota is too low and notifies via Telegram.

## Related pages

- [[Workflow-VideoProduction]]
- [[Workflow-RetentionFetch]]
- [[Security-Authn-Authz]]
