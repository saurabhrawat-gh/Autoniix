"""Auto-import all provider modules so they register with ProviderRegistry.

Every service that uses ProviderRegistry should import this module once:
    import providers.boot  # noqa: F401

Scripts that need an explicit call site can use ``boot_providers()``;
the function is a no-op because the registration happens as a side
effect of importing this module.
"""


def boot_providers() -> None:
    """Idempotent no-op. Provider registration happens at import time.

    Kept for callers that prefer an explicit function call over a bare
    module import (``scripts/run_prompt_eval.py``, ``curate_library.py``,
    ``import_local_assets.py``).
    """
    return None


import providers.image.dalle_provider  # noqa: F401
import providers.image.fal_flux_provider  # noqa: F401
import providers.image.stability_provider  # noqa: F401
import providers.llm.claude_provider  # noqa: F401
import providers.llm.custom_openai_compat_provider  # noqa: F401
import providers.llm.deepseek_provider  # noqa: F401
import providers.llm.gemini_provider  # noqa: F401
import providers.llm.glm_provider  # noqa: F401
import providers.llm.kimi_provider  # noqa: F401
import providers.llm.mock_provider  # noqa: F401  (test mode)
import providers.llm.openai_provider  # noqa: F401
import providers.llm.openai_vision_provider  # noqa: F401
import providers.search.mock_search_provider  # noqa: F401  (test mode)
import providers.search.serpapi_provider  # noqa: F401
import providers.stock.kling_provider  # noqa: F401
import providers.stock.pexels_provider  # noqa: F401
import providers.stock.pixabay_provider  # noqa: F401
import providers.stock.unsplash_provider  # noqa: F401
import providers.storage.minio_provider  # noqa: F401
import providers.tts.cartesia_provider  # noqa: F401
import providers.tts.edge_tts_provider  # noqa: F401  (free fallback)
import providers.tts.elevenlabs_provider  # noqa: F401
import providers.tts.fish_audio  # noqa: F401
import providers.tts.inworld_tts_provider  # noqa: F401
