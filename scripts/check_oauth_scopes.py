"""Check that the configured Google OAuth refresh token has the required YouTube Analytics scope.

Required scope: https://www.googleapis.com/auth/yt-analytics.readonly

Without it, RetentionFetchWorkflow (Phase 9) fails with 403 on every video.
Run this before go-live and after every OAuth re-authorisation.

Usage:
    python -m scripts.check_oauth_scopes
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from core.config import settings

REQUIRED_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


async def main() -> None:
    print("Checking Google OAuth scopes …\n")

    if not all(
        [
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
            settings.google_oauth_refresh_token,
        ]
    ):
        print("❌  OAuth credentials not configured.", file=sys.stderr)
        print("    Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET,", file=sys.stderr)
        print("    and GOOGLE_OAUTH_REFRESH_TOKEN in your .env file.", file=sys.stderr)
        sys.exit(1)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": settings.google_oauth_refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if resp.status_code != 200:
        print(f"❌  OAuth token refresh failed: {resp.status_code}", file=sys.stderr)
        print(f"    {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)

    token = resp.json().get("access_token")
    if not token:
        print("❌  OAuth response missing access_token", file=sys.stderr)
        sys.exit(1)

    print("✅  Refresh token valid — got access token.\n")

    async with httpx.AsyncClient(timeout=10.0) as client:
        info = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": token},
        )

    if info.status_code != 200:
        print(f"❌  tokeninfo failed: {info.status_code}", file=sys.stderr)
        sys.exit(1)

    granted = set(info.json().get("scope", "").split())

    print(f"Granted scopes ({len(granted)}):")
    for s in sorted(granted):
        tag = "✅" if s in (REQUIRED_SCOPE, UPLOAD_SCOPE) else "  "
        print(f"  {tag}  {s}")

    print()
    if REQUIRED_SCOPE in granted:
        print(f"✅  PASS — required scope is present: {REQUIRED_SCOPE}")
    else:
        print(f"❌  FAIL — missing required scope: {REQUIRED_SCOPE}", file=sys.stderr)
        print(
            "\nFix: Re-authorise the YouTube OAuth flow at\n"
            "  GET /api/v2/providers/youtube/oauth/init\n"
            "and tick 'YouTube Analytics (read-only)' on the Google consent screen.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
