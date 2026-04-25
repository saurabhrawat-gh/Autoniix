from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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
    tts_provider: str = "fish_audio"

    # ── Search ──────────────────────────────────────────
    serpapi_key: str = ""
    search_provider: str = "serpapi"

    # ── Image ───────────────────────────────────────────
    pixabay_api_key: str = ""
    image_provider: str = "dalle"

    # ── Storage ─────────────────────────────────────────
    storage_provider: str = "minio"

    # ── LLM Routing ─────────────────────────────────────
    llm_provider: str = "openai"
    llm_research_provider: str = "openai"
    llm_script_provider: str = "openai"
    llm_factcheck_provider: str = "openai"
    llm_qc_provider: str = "openai"

    # ── Temporal ────────────────────────────────────────
    temporal_host: str = "temporal:7233"
    temporal_namespace: str = "default"

    # ── Remotion ────────────────────────────────────────
    remotion_base_url: str = "http://remotion:4000"

    # ── YouTube / Google OAuth ────────────────────────
    youtube_api_key: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""

    # ── Admin ───────────────────────────────────────────
    admin_jwt_secret: str = "change_me"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()
