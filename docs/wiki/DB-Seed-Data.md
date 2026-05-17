# Database Seed Data

## Source

- `scripts/seed-data.sql` — idempotent inserts/upserts for
  `system_config` and `prompt_registry`.

## system_config (selected keys)

| Key | Default | Notes |
|---|---|---|
| `environment_mode` | `test` | toggled by `/system/environment` |
| `emergency_stop` | `FALSE` | red button |
| `daily_budget_limit_usd` | `5.00` | production cap |
| `max_videos_per_day` | `30` | production cap |
| `test_daily_budget_limit` | `5.00` | test cap |
| `test_max_videos_per_day` | `10` | test cap |
| `dashboard_admin_password` | `change_me` | legacy auth |
| `auth.legacy.enabled` | `TRUE` | dual-mode |
| `auth.v2.enabled` | `FALSE` | flip via `make auth-enable` |
| `auth.multi_tenant.enabled` | `FALSE` | set by migration |
| `gate_threshold_<niche>_<dim>` | varies | tuned by gate-calibration |
| `opportunity_weights` | JSON | per-feature weights |
| `telegram_bot_token` / `telegram_chat_id` | `` | notifications |
| `notify_*` | `TRUE/FALSE` | per-event prefs |

## prompt_registry

Versioned LLM prompts. Each entry has a `prompt_key` (e.g.
`script.v1`, `script.critique`, `direction`, `thumbnail`,
`voice.emotion`) and a `version`. Only one row per key is `active=TRUE`.
The full set of 12 prompts was upgraded to v2 during the Quality &
Automation Upgrade (see memory notes / `docs/QA-PROVIDERS.md`).

## Reseeding

`seed-data.sql` uses `ON CONFLICT (config_key) DO UPDATE SET
config_value = EXCLUDED.config_value` so editing the file and re-running
the seed actually applies the new defaults (which is unusual — most seed
scripts are insert-only). Same pattern for `prompt_registry` keyed on
`(prompt_key, version)`.

## Related pages

- [[DB-Schema]] · [[Service-Admin]] · [[Appendix-Env-Vars]]
