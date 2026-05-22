#!/usr/bin/env python3
"""Phase 9: Remove Epic parent link from all Task issues.

Tasks already have a 'relates to' link to their Story (Phase 8).
They should NOT also be parented to an Epic — that's the Story's job.

Sets parent=null on every Task that currently has an Epic as parent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _atlassian import AtlassianClient, load_config, get_state_dir

ISSUE_MAP_FILE = get_state_dir() / "issue_map.json"
GH_REPO = "saurabhrawat-gh/Autoniix"

GH_LABEL_TO_TYPE = {
    "type:epic": "Epic", "type:story": "Story",
    "type:task": "Task", "type:bug": "Bug",
}


def gh_fetch_all() -> dict[int, dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", GH_REPO, "--state", "all",
         "--limit", "1000", "--json", "number,labels"],
        capture_output=True, text=True, check=True,
    )
    return {i["number"]: i for i in json.loads(out.stdout)}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute

    cfg    = load_config()
    client = AtlassianClient(cfg, requests_per_second=5.0)
    issue_map: dict[int, str] = {
        int(k): v for k, v in json.loads(ISSUE_MAP_FILE.read_text()).items()
    }

    print(f"== Phase 9: Remove Epic parent from Tasks ({'DRY-RUN' if dry_run else 'EXECUTE'}) ==\n")

    print("Fetching GitHub issue labels...")
    gh_issues = gh_fetch_all()

    # Identify all Task keys
    task_keys: list[str] = []
    for gh_num, jira_key in issue_map.items():
        gh = gh_issues.get(gh_num, {})
        gh_lbls = [l["name"] for l in gh.get("labels", [])]
        itype = "Task"
        for lbl, tp in GH_LABEL_TO_TYPE.items():
            if lbl in gh_lbls:
                itype = tp
                break
        if itype == "Task":
            task_keys.append(jira_key)

    print(f"  Found {len(task_keys)} Tasks\n")

    removed = skipped = errors = 0

    for key in sorted(task_keys):
        # Check current parent
        try:
            data = client.jira_get(f"/issue/{key}?fields=parent,issuetype")
        except Exception as e:
            print(f"  ! {key}: fetch failed — {e}")
            errors += 1
            continue

        parent = data["fields"].get("parent")
        if not parent:
            skipped += 1
            continue  # already no parent

        parent_type = parent["fields"]["issuetype"]["name"]
        parent_key  = parent["key"]

        if parent_type != "Epic":
            skipped += 1
            continue  # parent is not an Epic, leave it

        print(f"  {key}  remove parent {parent_key} ({parent_type})")

        if dry_run:
            removed += 1
            continue

        r = client.request(
            "PUT", f"{client.cfg.jira_api}/issue/{key}",
            json_body={"fields": {"parent": None}},
        )
        if r.status_code >= 400:
            print(f"    !! failed: {r.status_code}: {r.text[:200]}")
            errors += 1
        else:
            removed += 1

    print(f"\n== Done. Removed: {removed}  Skipped (no/non-epic parent): {skipped}  Errors: {errors} ==")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
