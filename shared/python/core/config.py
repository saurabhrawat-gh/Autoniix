from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "postgres-app"
    db_port: int = 5432
    db_name: str = "autoniix"
    db_user: str = "app"
    db_password: str = "change_me_strong_random_64"

    redis_url: str = "redis://redis:6379"

    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "autoniix"
    s3_public_base_url: str = ""
    s3_force_path_style: bool = True

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_ai_api_key: str = ""
    deepseek_api_key: str = ""

    fish_audio_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    inworld_api_key: str = ""
    inworld_tts_model: str = "inworld-tts-2"
    inworld_voice_id: str = "Ashley"  # Inworld stock voice; override per channel or via INWORLD_VOICE_ID
    cartesia_api_key: str = ""
    tts_provider: str = "inworld"

    serpapi_key: str = ""
    news_api_key: str = ""
    search_provider: str = "serpapi"

    pixabay_api_key: str = ""
    pexels_api_key: str = ""
    unsplash_api_key: str = ""
    kling_api_key: str = ""
    freesound_api_key: str = ""
    stability_api_key: str = ""
    image_provider: str = "openai_dalle"

    storage_provider: str = "minio"

    finishing_service_url: str = "http://resolve-finisher:8014"

    llm_openai_model: str = "gpt-4o-mini"
    llm_claude_model: str = "claude-sonnet-4-20250514"
    llm_gemini_model: str = "gemini-2.5-flash"
    llm_deepseek_model: str = "deepseek-chat"
    llm_provider: str = "deepseek"
    llm_research_provider: str = "gemini"
    llm_script_provider: str = "claude"
    llm_factcheck_provider: str = "claude"
    llm_qc_provider: str = "gemini"
    llm_vision_provider: str = "openai"
    llm_ideation_provider: str = "gemini"
    llm_hook_provider: str = "gemini"
    llm_direction_provider: str = "claude"
    llm_emotion_provider: str = "gemini"

    llm_compression: str = "off"
    llm_prune_max_tokens: int = 8000
    llm_llmlingua_ratio: float = 0.35
    llm_compress_min_tokens: int = 200

    temporal_host: str = "temporal:7233"
    temporal_namespace: str = "default"
    temporal_production_max_activities: int = 5
    temporal_production_max_workflow_tasks: int = 10
    temporal_scheduler_max_activities: int = 3
    temporal_default_activity_start_to_close_s: int = 1800
    temporal_default_activity_heartbeat_s: int = 60

    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    db_statement_timeout_ms: int = 30_000
    db_pool_acquire_timeout_s: float = 10.0

    remotion_base_url: str = "http://remotion-api:4000"

    youtube_api_key: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""
    google_oauth_redirect_uri: str = "https://dash.autoniix.com/api/v2/providers/youtube/callback"

    google_sheets_id: str = "11-vlRvjXfDVLQMnrHzuujE5A1i4luy2DG-ycUtsS-c4"
    google_sheets_credentials_json: str = ""

    admin_jwt_secret: str = "change_me"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
