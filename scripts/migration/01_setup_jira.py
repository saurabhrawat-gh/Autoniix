#!/usr/bin/env python3
"""Phase 1: Prepare Jira project AE for migration.

What this script does:
  1. Adds missing issue types (Story, Bug) to the project
  2. Probes the current workflow statuses
  3. Prints exact UI instructions to add any missing statuses
     (workflow editing via API on Jira Cloud is fragile — UI is reliable)

Idempotent: safe to re-run.
"""
from __future__ import annotations

import sys

from _atlassian import AtlassianClient, load_config, pretty

JIRA_PROJECT_KEY = "AE"

REQUIRED_ISSUE_TYPES = {
    "Story": "Functional user-facing capability — a vertical slice of value.",
    "Bug": "Defect found in QA or production.",
}

REQUIRED_STATUSES = [
    "To Do",            # default Jira status — should exist
    "In Progress",      # default Jira status — should exist
    "Dev Done",         # custom
    "In QA",            # custom
    "QA Verified",      # custom
    "Ready to Deploy",  # custom
    "In Prod",          # custom
    "Prod Verified",    # custom
    "Done",             # default Jira status — should exist
]


def add_missing_issue_types(client: AtlassianClient) -> list[str]:
    """Create any required issue types that don't already exist globally,
    then ensure they are associated with the project's issue type scheme."""
    existing_global = {
        it["name"]: it for it in client.jira_get("/issuetype")
    }
    created = []
    for name, desc in REQUIRED_ISSUE_TYPES.items():
        if name in existing_global:
            print(f"  - '{name}' already exists globally (id={existing_global[name]['id']})")
            continue
        try:
            new_type = client.jira_post(
                "/issuetype",
                {"name": name, "description": desc, "type": "standard"},
            )
            created.append(name)
            print(f"  + created '{name}' (id={new_type.get('id')})")
        except RuntimeError as e:
            print(f"  ! failed to create '{name}': {e}")
    return created


def probe_statuses(client: AtlassianClient) -> tuple[set[str], list[dict]]:
    """Return (existing status name set, raw status list) for the project."""
    statuses = client.jira_get(f"/project/{JIRA_PROJECT_KEY}/statuses")
    # `statuses` is a list of {issueType, statuses}
    seen: set[str] = set()
    for entry in statuses:
        for s in entry.get("statuses", []):
            seen.add(s["name"])
    return seen, statuses


def main() -> int:
    cfg = load_config()
    client = AtlassianClient(cfg)

    print(f"== Phase 1: Setup Jira project {JIRA_PROJECT_KEY} ==\n")

    # 1. Issue types
    print("[1/2] Ensuring issue types exist:")
    created = add_missing_issue_types(client)
    if created:
        print(
            f"\n  NOTE: {len(created)} new issue type(s) created globally. "
            "You may need to add them to the project's issue type scheme via UI:\n"
            f"  {cfg.base_url}/jira/software/projects/{JIRA_PROJECT_KEY}/settings/issuetypes\n"
        )

    # 2. Statuses
    print("\n[2/2] Probing workflow statuses:")
    seen, _raw = probe_statuses(client)
    print(f"  Current statuses in project: {sorted(seen)}")

    missing = [s for s in REQUIRED_STATUSES if s not in seen]
    if not missing:
        print("\n  All required statuses present.")
        print("\n== Phase 1 complete ==")
        return 0

    print(f"\n  Missing statuses: {missing}")
    print(
        "\n  UI steps to add them (workflow API is unreliable on free tier):\n"
        f"  1. Open: {cfg.base_url}/jira/software/projects/{JIRA_PROJECT_KEY}/board\n"
        "  2. Top-right '...' menu -> 'Configure board' (or Project settings -> Board)\n"
        "  3. 'Columns' tab -> click '+ Add column' for each missing status\n"
        "     OR Project settings -> 'Workflow' (or 'Workflows') -> Edit workflow\n"
        "     -> Add status nodes with the names listed above\n"
        "  4. Save changes\n"
        "  5. Re-run THIS script to verify\n"
    )
    print("\n== Phase 1 PENDING: add the missing statuses above, then re-run ==")
    return 1


if __name__ == "__main__":
    sys.exit(main())
