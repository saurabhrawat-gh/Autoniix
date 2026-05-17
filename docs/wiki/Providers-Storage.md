# Providers: Storage

## Purpose

Object storage — wraps MinIO with environment-aware key prefixing and a
helper for bulk cleanup.

## Source

- `src/providers/storage/base.py`
- `src/providers/storage/minio_provider.py`

## ABC

```python
class StorageProvider(ABC):
    async def put(key, body, *, content_type, public=False) -> str: ...
    async def get(key) -> bytes: ...
    async def presign(key, *, expires_s=3600, method="GET") -> str: ...
    async def delete(key) -> None: ...
    async def delete_prefix(prefix) -> int: ...
    async def list(prefix) -> list[str]: ...
    async def health_check() -> bool: ...
    def provider_name() -> str: ...
```

## Key prefixing

Every put auto-prefixes with `prod/` or `test/` based on
`environment.get_storage_prefix()`. Combined with `public/`-policy on the
MinIO bucket, the final layout is:

```
s3://autoniix/
  prod/...
  test/...
  public/...           ← anonymously readable (thumbnails for YouTube)
```

`delete_prefix("test/")` is exposed via the dashboard `DELETE /api/test-data`
for clean-slate test runs.

## Tee writer (deferred)

`storage-failover` (`PENDING.md`) will add a `tee` provider that writes to
MinIO + Cloudflare R2 in parallel. Not yet implemented — trigger is the
first MinIO outage.

## Related pages

- [[Architecture-Data-Layer]] · [[Test-vs-Production-Mode]]
