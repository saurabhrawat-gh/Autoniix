"""AE-33 — YouTube OAuth2 PKCE flow.

Endpoints (all under /api/v2/providers/youtube/):
  GET  /auth       → redirect to Google OAuth consent screen
  GET  /callback   → exchange code for tokens, store, SSE push, close popup
  GET  /status     → connection status + channel info for the dashboard card
  DELETE /disconnect  → delete stored tokens

OAuth scopes:
  - https://www.googleapis.com/auth/youtube.upload
  - https://www.googleapis.com/auth/youtube
  - https://www.googleapis.com/auth/yt-analytics.readonly

Tokens are stored via put_secret_at():
  - path: youtube/oauth/{workspace_id}
  - keys: access_token, refresh_token

Channel metadata (id, name, avatar) is written into
provider_credentials.extra_config when a connection is created.

WARNING: access_token is NEVER returned in any API response.
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.parse
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.config import settings
from src.providers.secrets import get_secret_at, put_secret_at
from src.db import get_pool

from ._deps import Principal, audit, principal_dep, require_role

logger = structlog.get_logger()
router = APIRouter()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "openid",
    "email",
    "profile",
]

_VAULT_PATH = "youtube/oauth"


def _token_path(workspace_id: int) -> str:
    return f"{_VAULT_PATH}/{workspace_id}"


def _missing_scope_names(granted_scope: str) -> list[str]:
    required = {
        "youtube.upload": "https://www.googleapis.com/auth/youtube.upload",
        "youtube": "https://www.googleapis.com/auth/youtube",
    }
    return [name for name, uri in required.items() if uri not in granted_scope]


async def _refresh_access_token(workspace_id: int) -> str | None:
    """Use stored refresh token to get a new access token. Updates vault."""
    refresh_token = get_secret_at(_token_path(workspace_id), "refresh_token")
    if not refresh_token:
        return None
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        logger.warning("youtube.oauth.refresh_failed", status=resp.status_code, body=resp.text)
        return None
    data = resp.json()
    access_token = data.get("access_token")
    if access_token:
        put_secret_at(_token_path(workspace_id), "access_token", access_token)
    return access_token


async def _get_valid_token(workspace_id: int) -> str | None:
    """Return a valid access token, refreshing if needed."""
    token = get_secret_at(_token_path(workspace_id), "access_token")
    if token:
        return token
    return await _refresh_access_token(workspace_id)


async def _fetch_channel_info(access_token: str) -> dict[str, Any]:
    """Fetch connected channel id, name, and avatar."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            _YT_CHANNELS_URL,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        return {}
    items = resp.json().get("items", [])
    if not items:
        return {}
    ch = items[0]
    return {
        "channel_id":     ch["id"],
        "channel_name":   ch["snippet"]["title"],
        "channel_avatar": ch["snippet"]["thumbnails"].get("default", {}).get("url"),
    }


# ---------------------------------------------------------------------------
# GET /auth  — initiate OAuth flow (called from popup)
# ---------------------------------------------------------------------------

@router.get("/auth")
async def youtube_auth(
    actor: Principal = Depends(require_role("owner")),
):
    """Redirect to Google OAuth consent screen."""
    if not settings.google_oauth_client_id:
        raise HTTPException(503, "GOOGLE_OAUTH_CLIENT_ID is not configured")

    params = {
        "client_id":     settings.google_oauth_client_id,
        "redirect_uri":  settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope":         " ".join(_SCOPES),
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         str(actor.workspace_id),
    }
    url = f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


# ---------------------------------------------------------------------------
# GET /callback  — Google redirects here after consent
# ---------------------------------------------------------------------------

@router.get("/callback")
async def youtube_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """Exchange auth code for tokens; close popup via JS."""
    if error or not code:
        html = f"""<html><body><script>
        window.opener?.postMessage({{type:'youtube_oauth',ok:false,error:{json.dumps(error or 'no_code')}}}, '*');
        window.close();
        </script><p>Connection failed: {error or 'no_code'}. You may close this window.</p></body></html>"""
        return HTMLResponse(html)

    workspace_id = int(state) if state and state.isdigit() else 0

    # Exchange code for tokens
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri":  settings.google_oauth_redirect_uri,
            "grant_type":    "authorization_code",
        })

    if resp.status_code != 200:
        logger.error("youtube.oauth.token_exchange_failed", status=resp.status_code)
        html = """<html><body><script>
        window.opener?.postMessage({type:'youtube_oauth',ok:false,error:'token_exchange_failed'}, '*');
        window.close();
        </script><p>Token exchange failed. You may close this window.</p></body></html>"""
        return HTMLResponse(html)

    token_data = resp.json()
    access_token  = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    granted_scope = token_data.get("scope", "")

    # Store tokens in vault/secrets backend; fall back to DB extra_config if backend is read-only
    _tokens_in_db: dict[str, str] = {}
    if access_token:
        try:
            put_secret_at(_token_path(workspace_id), "access_token", access_token)
        except NotImplementedError:
            _tokens_in_db["access_token"] = access_token
    if refresh_token:
        try:
            put_secret_at(_token_path(workspace_id), "refresh_token", refresh_token)
        except NotImplementedError:
            _tokens_in_db["refresh_token"] = refresh_token

    # Fetch channel info
    channel_info = await _fetch_channel_info(access_token) if access_token else {}
    missing_scopes = _missing_scope_names(granted_scope)

    # Persist channel metadata + scope info in provider_credentials
    if channel_info and workspace_id:
        try:
            pool = await get_pool()
            existing = await pool.fetchval(
                """SELECT id FROM provider_credentials
                    WHERE category='youtube' AND provider_name='youtube_oauth'
                      AND channel_id IS NULL
                      AND (extra_config->>'workspace_id')::int=$1""",
                workspace_id,
            )
            extra = {
                **channel_info,
                **_tokens_in_db,
                "workspace_id": workspace_id,
                "missing_scopes": missing_scopes,
                "connected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if existing:
                await pool.execute(
                    "UPDATE provider_credentials SET extra_config=$1::jsonb WHERE id=$2",
                    json.dumps(extra), existing,
                )
            else:
                await pool.execute(
                    """INSERT INTO provider_credentials
                       (workspace_id, category, provider_name, label, vault_path,
                        extra_config, enabled)
                       VALUES ($1,'youtube','youtube_oauth',$2,$3,$4::jsonb,TRUE)""",
                    workspace_id,
                    channel_info.get("channel_name", "YouTube"),
                    _token_path(workspace_id),
                    json.dumps(extra),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("youtube.oauth.db_write_failed", error=str(exc))

    # Close popup and notify opener
    payload = json.dumps({
        "type": "youtube_oauth",
        "ok": True,
        "channel_name": channel_info.get("channel_name", ""),
        "channel_avatar": channel_info.get("channel_avatar", ""),
        "missing_scopes": missing_scopes,
    })
    html = f"""<html><body><script>
    window.opener?.postMessage({payload}, '*');
    window.close();
    </script><p>Connected! You may close this window.</p></body></html>"""
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# GET /status  — connection status for the dashboard card
# ---------------------------------------------------------------------------

@router.get("/status")
async def youtube_status(
    actor: Principal = Depends(principal_dep),
):
    """Return connection status + channel info. Never returns tokens."""
    has_refresh = bool(get_secret_at(_token_path(actor.workspace_id), "refresh_token"))
    if not has_refresh:
        pool = await get_pool()
        _row = await pool.fetchrow(
            """SELECT extra_config FROM provider_credentials
                WHERE category='youtube' AND provider_name='youtube_oauth'
                  AND (extra_config->>'workspace_id')::int=$1""",
            actor.workspace_id,
        )
        _extra = dict(_row["extra_config"]) if _row and _row["extra_config"] else {}
        has_refresh = bool(_extra.get("refresh_token"))
    if not has_refresh:
        return {"status": "ok", "data": {"connected": False}}

    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT extra_config FROM provider_credentials
            WHERE category='youtube' AND provider_name='youtube_oauth'
              AND (extra_config->>'workspace_id')::int=$1""",
        actor.workspace_id,
    )
    extra = dict(row["extra_config"]) if row and row["extra_config"] else {}
    missing_scopes = extra.get("missing_scopes", [])

    return {"status": "ok", "data": {
        "connected":      True,
        "channel_name":   extra.get("channel_name"),
        "channel_avatar": extra.get("channel_avatar"),
        "channel_id":     extra.get("channel_id"),
        "connected_at":   extra.get("connected_at"),
        "missing_scopes": missing_scopes,
    }}


# ---------------------------------------------------------------------------
# DELETE /disconnect  — revoke & delete tokens
# ---------------------------------------------------------------------------

@router.delete("/disconnect")
async def youtube_disconnect(
    request: Request,
    actor: Principal = Depends(require_role("owner")),
):
    """Delete stored tokens and remove the credential row."""
    from src.providers.secrets import _backends

    path = _token_path(actor.workspace_id)
    deleted = 0
    for backend in _backends():
        try:
            n = backend.delete_prefix(path)
            deleted += n
        except Exception:  # noqa: BLE001
            pass

    pool = await get_pool()
    await pool.execute(
        """DELETE FROM provider_credentials
            WHERE category='youtube' AND provider_name='youtube_oauth'
              AND (extra_config->>'workspace_id')::int=$1""",
        actor.workspace_id,
    )

    await audit(
        actor=actor, action="provider.youtube.disconnect",
        target_type="youtube_oauth", target_id=str(actor.workspace_id),
        after={"deleted_secrets": deleted}, request=request,
    )
    return {"status": "ok", "data": {"disconnected": True}}
