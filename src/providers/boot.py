"""Auto-import all provider modules so they register with ProviderRegistry.

Every service that uses ProviderRegistry should import this module once:
    import src.providers.boot  # noqa: F401
"""

# LLM Providers
import src.providers.llm.openai_provider       # noqa: F401
import src.providers.llm.openai_vision_provider # noqa: F401
import src.providers.llm.claude_provider        # noqa: F401
import src.providers.llm.gemini_provider        # noqa: F401
import src.providers.llm.glm_provider           # noqa: F401  (Zhipu GLM, OpenAI-compatible)
import src.providers.llm.kimi_provider          # noqa: F401  (Moonshot Kimi, OpenAI-compatible)
import src.providers.llm.mock_provider          # noqa: F401  (test mode)

# TTS Providers
import src.providers.tts.fish_audio             # noqa: F401
import src.providers.tts.elevenlabs_provider    # noqa: F401
import src.providers.tts.edge_tts_provider      # noqa: F401  (test mode)

# Image Providers
import src.providers.image.dalle_provider       # noqa: F401
import src.providers.image.placeholder_provider # noqa: F401  (test mode)

# Search Providers
import src.providers.search.serpapi_provider    # noqa: F401
import src.providers.search.mock_search_provider # noqa: F401  (test mode)

# Storage Providers
import src.providers.storage.minio_provider     # noqa: F401
