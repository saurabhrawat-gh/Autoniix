"""GitHub REST API v3 client — branch, file, and PR operations."""

from __future__ import annotations

import base64

import httpx
import structlog
from config import (
    GITHUB_BASE_BRANCH,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
    GITHUB_TOKEN,
)

logger = structlog.get_logger()

_BASE = "https://api.github.com"
_REPO = f"{_BASE}/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"


class GitHubClient:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_branch_sha(self, branch: str = GITHUB_BASE_BRANCH) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{_REPO}/branches/{branch}", headers=self._headers)
            r.raise_for_status()
            sha: str = r.json()["commit"]["sha"]
            return sha

    async def create_branch(self, branch_name: str, from_branch: str = GITHUB_BASE_BRANCH) -> None:
        sha = await self.get_branch_sha(from_branch)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{_REPO}/git/refs",
                headers=self._headers,
                json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            )
            r.raise_for_status()
        logger.info("github.branch_created", branch=branch_name, from_branch=from_branch)

    async def get_file(self, path: str, ref: str = GITHUB_BASE_BRANCH) -> dict | None:
        """Return the GitHub contents API response for a file, or None if 404."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{_REPO}/contents/{path}",
                headers=self._headers,
                params={"ref": ref},
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    async def update_file(
        self,
        *,
        path: str,
        new_content: str,
        commit_message: str,
        branch: str,
        blob_sha: str,
    ) -> None:
        """Commit a full file replacement on the given branch."""
        encoded = base64.b64encode(new_content.encode()).decode()
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.put(
                f"{_REPO}/contents/{path}",
                headers=self._headers,
                json={
                    "message": commit_message,
                    "content": encoded,
                    "sha": blob_sha,
                    "branch": branch,
                },
            )
            r.raise_for_status()
        logger.info("github.file_updated", path=path, branch=branch)

    async def create_pr(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str = GITHUB_BASE_BRANCH,
    ) -> dict:
        """Open a pull request and return the PR object."""
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{_REPO}/pulls",
                headers=self._headers,
                json={"title": title, "body": body, "head": head, "base": base},
            )
            r.raise_for_status()
            pr: dict = r.json()
        logger.info("github.pr_created", url=pr.get("html_url"), head=head, base=base)
        return pr
