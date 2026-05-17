# Providers: Image

## Purpose

Text→image generation, primarily for thumbnails and stylised cutaways.
Fallback path when stock footage doesn’t fit.

## Source

- `src/providers/image/base.py`
- `src/providers/image/dalle_provider.py` (default production)
- `src/providers/image/placeholder_provider.py` (test mode, Pillow-generated)

## ABC

```python
class ImageProvider(ABC):
    async def generate(prompt, *, width, height, n=1, style=None) -> list[bytes]: ...
    def estimate_cost(width, height, n) -> float: ...
    async def health_check() -> bool: ...
    def provider_name() -> str: ...
```

## DALL·E

Uses OpenAI Images API (`gpt-image-1` or `dall-e-3`). Cost ~$0.04 per
1024×1024 standard image. Vision QC by gpt-4o-vision can request a
regeneration with a refined prompt.

## Placeholder (test mode)

Pillow generates a labelled solid-colour 1024×1024 PNG annotated with the
prompt text and content_id so visual smoke tests can read it back.
Zero cost.

## Related pages

- [[Service-Thumbnail]] · [[Service-Assets]]
