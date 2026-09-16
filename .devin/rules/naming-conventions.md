# Naming Conventions

## Python

- Files: `snake_case.py` (e.g., `script_analyzer.py`, `burst_detector.py`)
- Functions/variables: `snake_case` (e.g., `calculate_discount`, `accrued_cost`)
- Classes: `PascalCase` (e.g., `ProviderRegistry`, `VideoProductionWorkflow`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `RETRY_STANDARD`, `_TEST_PROVIDER_MAP`)
- Private module-level: prefix `_` (e.g., `_ENV_MAP`, `_add_cost`)
- Pydantic models: `PascalCase` with descriptive suffix (e.g., `VideoParams`, `LLMRequest`)

## Provider Pattern Naming

- ABC base: `<Category>Provider` (e.g., `LLMProvider`, `TTSProvider`)
- Concrete: `<Name><Category>` (e.g., `ClaudeLLM`, `FishAudioTTS`, `MockLLM`)
- Registry key: `category.name` (e.g., `llm.script`, `tts.fishaudio`)
- Config key: `<category>_provider` (e.g., `llm_provider`, `tts_provider`)

## Temporal

- Workflow class: `PascalCaseWorkflow` (e.g., `VideoProductionWorkflow`)
- Activity functions: `snake_case` (e.g., `run_research`, `emit_job_event`)
- Signal methods: `snake_case` (e.g., `pause_workflow`, `approve_video`)
- Query methods: `get_<thing>` (e.g., `get_status`)

## Database

- Tables: `snake_case` plural (e.g., `channels`, `videos`, `script_features`)
- Columns: `snake_case` (e.g., `channel_id`, `created_at`)
- Indexes: `idx_<table>_<columns>` (e.g., `idx_videos_status`)
- JSONB columns: `config`, `scores`, `artifacts`, `metadata`

## Docker

- Service names: `kebab-case` (e.g., `postgres-app`, `production-worker`, `dashboard-bff`)
- Environment variables: `UPPER_SNAKE_CASE` (e.g., `DB_HOST`, `OPENAI_API_KEY`)

## Content IDs

- Videos: `VID_<CHANNEL>_<DATE>_<SEQ>` (e.g., `VID_BS001_20250425_001`)
- Test videos: `TEST_VID_<CHANNEL>_<DATE>_<SEQ>`
- Channels: alphanumeric ID (e.g., `BS001`)

## Import Style

- `from __future__ import annotations` at top of every file
- `from src.config import settings` for config access
- `from src.providers.registry import ProviderRegistry` for provider access
- `import structlog; logger = structlog.get_logger()` for logging
