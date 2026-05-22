#!/usr/bin/env python3
"""Read-only credential probe against Atlassian Jira + Confluence.

Validates:
  1. Credentials file readable
  2. Jira auth works (GET /myself)
  3. Confluence auth works (GET /spaces)
  4. Jira project ATNX exists and is writable (read project metadata)
  5. Confluence space ATNX exists

Exits 0 on success, non-zero otherwise. Creates ZERO data.
"""
from __future__ import annotations

import sys

from _atlassian import AtlassianClient, load_config

JIRA_PROJECT_KEY = "AE"
CONFLUENCE_SPACE_KEY = "AE"


def main() -> int:
    print("== Atlassian credential probe ==\n")
    cfg = load_config()
    print(f"Base URL : {cfg.base_url}")
    print(f"Email    : {cfg.email}")
    print(f"Token    : {cfg.token[:8]}... ({len(cfg.token)} chars)\n")

    client = AtlassianClient(cfg)

    # 1. Jira /myself
    print("[1/4] Jira auth ...", end=" ", flush=True)
    me = client.jira_get("/myself")
    print(f"OK  ->  {me.get('displayName')}  ({me.get('accountId')[:12]}...)")

    # 2. Jira project
    print(f"[2/4] Jira project {JIRA_PROJECT_KEY} ...", end=" ", flush=True)
    proj = client.jira_get(f"/project/{JIRA_PROJECT_KEY}")
    print(f"OK  ->  '{proj.get('name')}' (id={proj.get('id')})")

    # 3. Confluence spaces (list, filter by key)
    print(f"[3/4] Confluence space {CONFLUENCE_SPACE_KEY} ...", end=" ", flush=True)
    spaces = client.confluence_get("/spaces", params={"keys": CONFLUENCE_SPACE_KEY})
    results = spaces.get("results", [])
    if not results:
        print(f"FAIL  -> space '{CONFLUENCE_SPACE_KEY}' not found")
        return 3
    space = results[0]
    print(f"OK  ->  '{space.get('name')}' (id={space.get('id')})")

    # 4. Jira issue types available on project
    print("[4/4] Jira issue types ...", end=" ", flush=True)
    proj_full = client.jira_get(
        f"/project/{JIRA_PROJECT_KEY}",
        params={"expand": "issueTypes"},
    )
    types = [it["name"] for it in proj_full.get("issueTypes", [])]
    print(f"OK  ->  {types}")

    missing = [t for t in ("Epic", "Story", "Task", "Bug") if t not in types]
    if missing:
        print(
            f"\n  WARNING: missing issue types in project: {missing}\n"
            f"  Migration script will create them in Phase 1 setup."
        )
    else:
        print("\n  All required issue types (Epic/Story/Task/Bug) present.")

    print("\n== All checks passed ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
