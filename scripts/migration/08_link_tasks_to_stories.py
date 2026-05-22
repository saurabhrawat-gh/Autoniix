#!/usr/bin/env python3
"""Phase 8: Link every Task to its parent Story via a 'Relates' issue link.

Since Jira team-managed can't convert existing issues to Subtasks,
we use issue links as the next best thing to show Task→Story membership.

For each Task that has a parent Story:
  Creates:  Task  --[relates to]-->  Story

Idempotent: tracked in state/linked.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from _atlassian import AtlassianClient, load_config, get_state_dir

GH_REPO        = "saurabhrawat-gh/Autoniix"
ISSUE_MAP_FILE = get_state_dir() / "issue_map.json"
DONE_FILE      = get_state_dir() / "linked.json"

GH_LABEL_TO_TYPE = {
    "type:epic": "Epic", "type:story": "Story",
    "type:task": "Task",  "type:bug": "Bug",
}

GH_PARENT_RE = re.compile(
    r'(?:'
    r'\*\*Parent Story:\*\*\s*#(\d+)'
    r'|\*\*Tests for Story:\*\*\s*#(\d+)'
    r'|Tests for Story:\s*#(\d+)'
    r'|Tests for:\s*#(\d+)'
    r'|Parent Story:\s*#(\d+)'
    r'|\*\*Parent Epic:\*\*\s*#(\d+)'
    r'|Parent Epic:\s*#(\d+)'
    r'|\*\*Parent:\*\*\s*#(\d+)'
    r'|Parent:\s*#(\d+)'
    r')',
    re.IGNORECASE | re.MULTILINE,
)

AE_PARENT_RE = re.compile(
    r'(?:'
    r'\*\*(?:Parent Story|Tests for Story|Tests for|Parent Epic|Parent):\*\*\s*(AE-\d+)'
    r'|(?:Parent Story|Tests for Story|Tests for|Parent Epic|Parent):\s*(AE-\d+)'
    r')',
    re.IGNORECASE | re.MULTILINE,
)


def gh_fetch_all() -> dict[int, dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", GH_REPO, "--state", "all",
         "--limit", "1000", "--json", "number,title,body,labels,state"],
        capture_output=True, text=True, check=True,
    )
    return {i["number"]: i for i in json.loads(out.stdout)}


def find_story_parent_from_gh(body: str, issue_map: dict[int, str],
                               story_keys: set[str]) -> Optional[str]:
    m = GH_PARENT_RE.search(body or "")
    if not m:
        return None
    n = int(next(g for g in m.groups() if g))
    key = issue_map.get(n)
    return key if key in story_keys else None


def find_story_parent_from_jira_body(body: str, story_keys: set[str]) -> Optional[str]:
    m = AE_PARENT_RE.search(body or "")
    if not m:
        return None
    key = next(g for g in m.groups() if g)
    return key if key in story_keys else None


def get_jira_text_body(client: AtlassianClient, key: str) -> str:
    try:
        r = client.jira_get(f"/issue/{key}?fields=description")
        desc = r.get("fields", {}).get("description") or {}
        parts: list[str] = []
        def walk(node: dict) -> None:
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for c in node.get("content", []):
                walk(c)
        walk(desc)
        return " ".join(parts)
    except Exception:
        return ""


def create_link(client: AtlassianClient, task_key: str, story_key: str,
                dry_run: bool) -> bool:
    if dry_run:
        print(f"  [DRY] {task_key}  --[relates to]-->  {story_key}")
        return True
    try:
        client.jira_post("/issueLink", {
            "type": {"name": "Relates"},
            "inwardIssue":  {"key": task_key},
            "outwardIssue": {"key": story_key},
        })
        return True
    except RuntimeError as e:
        print(f"    !! link failed: {e}")
        return False


def load_done() -> dict:
    if not DONE_FILE.exists():
        return {}
    return json.loads(DONE_FILE.read_text())


def save_done(d: dict) -> None:
    DONE_FILE.write_text(json.dumps(d, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", type=str, default="")
    args = parser.parse_args()
    dry_run = not args.execute

    cfg    = load_config()
    client = AtlassianClient(cfg, requests_per_second=5.0)
    issue_map: dict[int, str] = {
        int(k): v for k, v in json.loads(ISSUE_MAP_FILE.read_text()).items()
    }
    done = load_done()
    only = {k.strip() for k in args.only.split(",") if k.strip()}

    print(f"== Phase 8: Link Tasks → Stories ({'DRY-RUN' if dry_run else 'EXECUTE'}) ==")
    print(f"Already linked: {len(done)}\n")

    print("Fetching GitHub issues...")
    gh_issues = gh_fetch_all()
    print(f"  {len(gh_issues)} issues\n")

    # Build sets of task keys and story keys from issue_map + GitHub labels
    task_map: dict[str, int] = {}   # jira_key → gh_num
    story_keys: set[str] = set()

    for gh_num, jira_key in issue_map.items():
        gh = gh_issues.get(gh_num, {})
        gh_lbls = [l["name"] for l in gh.get("labels", [])]
        itype = "Task"
        for lbl, tp in GH_LABEL_TO_TYPE.items():
            if lbl in gh_lbls:
                itype = tp
                break
        if itype == "Task":
            task_map[jira_key] = gh_num
        elif itype == "Story":
            story_keys.add(jira_key)

    print(f"  Tasks: {len(task_map)}  Stories: {len(story_keys)}\n")

    processed = errors = 0
    no_story = 0

    for jira_key, gh_num in sorted(task_map.items()):
        if only and jira_key not in only:
            continue
        if jira_key in done and not only:
            continue
        if args.limit and processed >= args.limit:
            print(f"\nReached limit ({args.limit}); stopping.")
            break

        gh = gh_issues.get(gh_num, {})
        # Find parent story: try GitHub body first (faster, no API call)
        story_key = find_story_parent_from_gh(
            gh.get("body", ""), issue_map, story_keys
        )
        # Fall back to current Jira description if GitHub didn't match
        if not story_key:
            jira_body = get_jira_text_body(client, jira_key)
            story_key = find_story_parent_from_jira_body(jira_body, story_keys)

        if not story_key:
            no_story += 1
            continue  # standalone task, no story to link

        ok = create_link(client, jira_key, story_key, dry_run)
        if ok:
            if not dry_run:
                done[jira_key] = story_key
                save_done(done)
            processed += 1
        else:
            errors += 1

    print(f"\n== Done. Linked: {processed}  Errors: {errors}  "
          f"No-story (skipped): {no_story}  Total: {len(done)} ==")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
