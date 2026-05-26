"""Central config — fails fast on missing required env vars."""
import os

# Slack (Socket Mode)
SLACK_BOT_TOKEN: str = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN: str = os.environ["SLACK_APP_TOKEN"]
SLACK_CRITICAL_CHANNEL_ID: str = os.environ["SLACK_CRITICAL_CHANNEL_ID"]
SLACK_WARNINGS_CHANNEL_ID: str = os.environ["SLACK_WARNINGS_CHANNEL_ID"]

# Sentry
SENTRY_AUTH_TOKEN: str = os.environ["SENTRY_AUTH_TOKEN"]
SENTRY_ORG_SLUG: str = os.environ.get("SENTRY_ORG_SLUG", "autoniix")
SENTRY_BASE_URL: str = os.environ.get("SENTRY_BASE_URL", "https://sentry.io/api/0")

# GitHub
GITHUB_TOKEN: str = os.environ["GITHUB_TOKEN"]
GITHUB_REPO_OWNER: str = os.environ.get("GITHUB_REPO_OWNER", "saurabhrawat-gh")
GITHUB_REPO_NAME: str = os.environ.get("GITHUB_REPO_NAME", "Autoniix")
GITHUB_BASE_BRANCH: str = os.environ.get("GITHUB_BASE_BRANCH", "develop")

# Jira
JIRA_CLOUD_ID: str = os.environ.get("JIRA_CLOUD_ID", "73672c49-7089-4f35-adde-e3fa0d1e438f")
JIRA_EMAIL: str = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN: str = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY: str = os.environ.get("JIRA_PROJECT_KEY", "AE")

# LLM (reuse existing key from .env)
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
LLM_MODEL: str = os.environ.get("SENTRY_AGENT_LLM_MODEL", "gpt-4o-mini")

# Redis
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379")
DEDUP_TTL_SECONDS: int = int(os.environ.get("SENTRY_DEDUP_TTL", str(7 * 24 * 3600)))
