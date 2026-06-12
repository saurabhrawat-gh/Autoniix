"""Auto-import all provider modules so they register with ProviderRegistry.

Every service that uses ProviderRegistry should import this module once:
    import src.providers.boot  # noqa: F401

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


# LLM Providers
import src.providers.llm.openai_provider       # noqa: F401
import src.providers.llm.openai_vision_provider # noqa: F401
import src.providers.llm.claude_provider        # noqa: F401
import src.providers.llm.gemini_provider        # noqa: F401
import src.providers.llm.deepseek_provider      # noqa: F401
import src.providers.llm.glm_provider           # noqa: F401
import src.providers.llm.kimi_provider          # noqa: F401
import src.providers.llm.mock_provider          # noqa: F401  (test mode)
import src.providers.llm.custom_openai_compat_provider  # noqa: F401

# TTS Providers
import src.providers.tts.inworld_tts_provider   # noqa: F401
import src.providers.tts.fish_audio             # noqa: F401
import src.providers.tts.elevenlabs_provider    # noqa: F401
import src.providers.tts.cartesia_provider      # noqa: F401
import src.providers.tts.edge_tts_provider      # noqa: F401  (free fallback)

# Image Providers
import src.providers.image.dalle_provider       # noqa: F401
import src.providers.image.stability_provider  # noqa: F401
import src.providers.image.fal_flux_provider    # noqa: F401

# Search Providers
import src.providers.search.serpapi_provider    # noqa: F401
import src.providers.search.mock_search_provider # noqa: F401  (test mode)

# Stock Providers
import src.providers.stock.pexels_provider      # noqa: F401
import src.providers.stock.pixabay_provider     # noqa: F401
import src.providers.stock.unsplash_provider     # noqa: F401
import src.providers.stock.kling_provider       # noqa: F401

# Storage Providers
import src.providers.storage.minio_provider     # noqa: F401
