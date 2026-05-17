# Service: Assets

## Purpose

Resolves per-segment asset queries to concrete media: stock footage from
Pexels/Pixabay, the local Motion Array library, or DALL·E as fallback.

## Port / source

- Port `8004`, memory 512M
- `src/services/assets/main.py`
- `query_optimizer.py` — expands queries with WordNet synonyms, applies
  negative keywords, scores results for relevance.

## Sources searched (in parallel)

1. **Pexels API** (free) — videos + photos
2. **Pixabay API** (free) — videos + photos
3. **Local library** — ingested via
   `scripts/import_local_assets.py` and queried by SBERT similarity
4. **DALL·E** — only if all three above return no usable match (or for
   stylised cutaways requested by the script)

Storyblocks and Envato Elements were removed from the codebase in May 2026.

## Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /search` | One-shot query, returns ranked candidates |
| `POST /resolve-script` | Resolves every segment in `script_assets` |
| `POST /upload-local` | Used by `import_local_assets.py` |

## Scoring

`score_asset_relevance` combines: SBERT cosine, tag overlap, motion match
(is it moving when the segment says “motion”?), aspect ratio fit, and
license filter. Lowest-scoring under threshold escalates to DALL·E.

## Output

Assets pinned to `s3://autoniix/<prefix>/assets/<content_id>/...`. The
resolved `script_assets` JSON is passed to the assembly service.

## Related pages

- [[Providers-Image]]
- [[Service-Assembly]]
- [[Service-Remotion]]
