# BFF: Library (DAM)

## Purpose

Digital Asset Manager for locally-managed stock footage and images.
Lets operators ingest manual downloads (e.g. Motion Array), tag them, and
make them discoverable to the assets service via SBERT similarity search.

## Source

- `src/services/dashboard/v2/library.py:1-500`
- Ingestion CLI: `scripts/import_local_assets.py`

## Endpoints (`/api/v2/library/...`)

| Method + Path | Role | Purpose |
|---|---|---|
| `GET    /library/assets?q=&type=&page=` | member+ | Search by text query (SBERT) or filter |
| `POST   /library/assets` | admin+ | Upload + index a new asset |
| `GET    /library/assets/{id}` | member+ | Detail + presigned URL |
| `PUT    /library/assets/{id}` | admin+ | Edit tags / description |
| `DELETE /library/assets/{id}` | admin+ | Remove from index + MinIO |
| `GET    /library/stats` | member+ | Counts by type / niche |

## Index

Each asset row in `library_assets` carries:

- `description` (operator-provided)
- `tags` text[]
- `embedding vector(384)` (SBERT all-MiniLM-L6-v2)
- `mime_type`, `duration_s`, `width`, `height`
- `license`, `source`

Search ranks by SBERT cosine plus tag overlap.

## Related pages

- [[Service-Assets]] · [[UI-Content-And-Library]]
