from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App Database
    db_host: str = "postgres-app"
    db_port: int = 5432
    db_name: str = "autoniix"
    db_user: str = "app"
    db_password: str = "change_me_strong_random_64"

    # Redis
    redis_url: str = "redis://redis:6379"

    # S3 / MinIO
    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "autoniix"
    s3_public_base_url: str = ""
    s3_force_path_style: bool = True

    # AI Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_ai_api_key: str = ""
    deepseek_api_key: str = ""

    # TTS
    fish_audio_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    inworld_api_key: str = ""
    inworld_tts_model: str = "inworld-tts-2"           # inworld-tts-2 ($0.025/1K) | inworld-tts-1 ($0.015/1K)
    inworld_voice_id: str = ""                         # set to your cloned/designed voice ID
    tts_provider: str = "inworld"

    # Search
    serpapi_key: str = ""
    news_api_key: str = ""
    search_provider: str = "serpapi"

    # Image / Stock Footage
    pixabay_api_key: str = ""
    pexels_api_key: str = ""
    freesound_api_key: str = ""
    falai_api_key: str = ""
    falai_flux_model: str = "fal-ai/flux/schnell"      # quality="standard" → b-roll
    falai_flux_hd_model: str = "fal-ai/flux/dev"        # quality="hd" → thumbnails
    # Motion Array assets are managed via the local library (no API).
    # Use scripts/import_local_assets.py to ingest manually downloaded assets.
    image_provider: str = "fal_flux"

    # Storage
    storage_provider: str = "minio"

    # Finishing pipeline (AE-293). Phase 1A uses ffmpeg in-process; the URL is
    # consumed by Phase 1B (DaVinci Resolve headless service) and is unused in 1A.
    finishing_service_url: str = "http://resolve-finisher:8014"

    # LLM Routing
    llm_openai_model: str = "gpt-4o-mini"
    llm_claude_model: str = "claude-sonnet-4-20250514"
    llm_gemini_model: str = "gemini-2.5-flash"
    llm_deepseek_model: str = "deepseek-chat"
    llm_provider: str = "deepseek"
    llm_research_provider: str = "gemini"
    llm_script_provider: str = "claude"
    llm_factcheck_provider: str = "openai"
    llm_qc_provider: str = "gemini"
    llm_vision_provider: str = "openai"
    llm_ideation_provider: str = "gemini"
    llm_hook_provider: str = "deepseek"
    llm_direction_provider: str = "deepseek"
    llm_emotion_provider: str = "gemini"

    # Temporal
    temporal_host: str = "temporal:7233"
    temporal_namespace: str = "default"
    # Phase 6 — scale-out knobs. Defaults match the previous hard-coded
    # values so existing deployments don't change behaviour silently;
    # ops scales by setting env vars instead of editing code.
    temporal_production_max_activities: int = 5
    temporal_production_max_workflow_tasks: int = 10
    temporal_scheduler_max_activities: int = 3
    # Default per-activity timeout. Render activity has its own much
    # larger ladder (60 min poll cap inside the activity body), so this
    # only constrains the smaller activities that should never run long.
    temporal_default_activity_start_to_close_s: int = 1800   # 30 min
    temporal_default_activity_heartbeat_s: int = 60

    # Postgres pool
    # The pool is *per-process*. Each FastAPI service + each Temporal
    # worker creates its own. With ~6 services and 2 workers, the
    # default of max=10 caps the fleet at ~80 simultaneous DB ops —
    # which is plenty for a single-box Postgres but should be tuned
    # down on Postgres-per-tenant SaaS deployments.
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    # Hard ceiling per query — protects against runaway scans hanging
    # an activity forever. asyncpg ms; Postgres applies via SET LOCAL.
    db_statement_timeout_ms: int = 30_000
    # Per-acquire ceiling — if the pool is saturated, fail fast rather
    # than letting requests pile up.
    db_pool_acquire_timeout_s: float = 10.0

    # Remotion
    remotion_base_url: str = "http://remotion-api:4000"

    # YouTube / Google OAuth
    youtube_api_key: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""
    google_oauth_redirect_uri: str = "https://dash.autoniix.com/api/v2/providers/youtube/callback"

    # Google Sheets Sync
    google_sheets_id: str = "11-vlRvjXfDVLQMnrHzuujE5A1i4luy2DG-ycUtsS-c4"
    google_sheets_credentials_json: str = ""

    # Admin
    admin_jwt_secret: str = "change_me"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
