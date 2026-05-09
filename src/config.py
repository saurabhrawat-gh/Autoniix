from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Environment Mode ──────────────────────────────────
    environment_mode: str = "test"  # "test" or "production"

    # ── App Database ─────────────────────────────────────
    db_host: str = "postgres-app"
    db_port: int = 5432
    db_name: str = "yt_automation"
    db_user: str = "app"
    db_password: str = "change_me"

    # ── Redis ────────────────────────────────────────────
    redis_url: str = "redis://redis:6379"

    # ── S3 / MinIO ──────────────────────────────────────
    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "yt-automation"
    s3_public_base_url: str = ""
    s3_force_path_style: bool = True

    # ── AI Providers ────────────────────────────────────
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_ai_api_key: str = ""

    # ── TTS ─────────────────────────────────────────────
    fish_audio_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    tts_provider: str = "fishaudio"

    # ── Search ──────────────────────────────────────────
    serpapi_key: str = ""
    news_api_key: str = ""
    search_provider: str = "serpapi"

    # ── Image / Stock Footage ─────────────────────────────
    pixabay_api_key: str = ""
    pexels_api_key: str = ""
    envato_api_key: str = ""
    freesound_api_key: str = ""
    image_provider: str = "dalle"

    # ── Storage ─────────────────────────────────────────
    storage_provider: str = "minio"

    # ── LLM Routing ─────────────────────────────────────
    llm_provider: str = "openai"
    llm_research_provider: str = "gemini"
    llm_script_provider: str = "claude"
    llm_factcheck_provider: str = "openai"
    llm_qc_provider: str = "gemini"
    llm_vision_provider: str = "openai"
    llm_ideation_provider: str = "openai"
    llm_hook_provider: str = "openai"
    llm_direction_provider: str = "openai"
    llm_emotion_provider: str = "openai"

    # ── Temporal ────────────────────────────────────────
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

    # ── Postgres pool ──────────────────────────────────
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

    # ── Remotion ────────────────────────────────────────
    remotion_base_url: str = "http://remotion-api:4000"

    # ── YouTube / Google OAuth ────────────────────────
    youtube_api_key: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""

    # ── Google Sheets Sync ────────────────────────────
    google_sheets_id: str = "11-vlRvjXfDVLQMnrHzuujE5A1i4luy2DG-ycUtsS-c4"
    google_sheets_credentials_json: str = ""

    # ── Admin ───────────────────────────────────────────
    admin_jwt_secret: str = "change_me"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
