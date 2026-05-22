#!/usr/bin/env python3
"""Phase 7: Convert Task issues to Subtasks so they sit under their parent Story.

In Jira team-managed projects:
  - Epic  (level 1)
  - Story (level 0)   → parent: Epic
  - Task  (level 0)   ← SAME level as Story, cannot be child of Story
  - Subtask (level -1) → parent: Story  ✓

This script:
  1. Finds every Task in the AE project
  2. Determines its parent Story from the issue body (AE-X reference)
  3. Converts the Task to a Subtask and sets parent = Story
  4. Tasks with NO story parent (standalone) stay as Tasks under their Epic

Idempotent: state tracked in state/subtasks.json
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
DONE_FILE      = get_state_dir() / "subtasks.json"

# Matches AE-N refs that point to a parent story/epic in the cleaned body
AE_PARENT_RE = re.compile(
    r'(?:'
    r'\*\*Parent Story:\*\*\s*(AE-\d+)'
    r'|\*\*Tests for Story:\*\*\s*(AE-\d+)'
    r'|Tests for Story:\s*(AE-\d+)'
    r'|Tests for:\s*(AE-\d+)'
    r'|Parent Story:\s*(AE-\d+)'
    r'|Parent Epic:\s*(AE-\d+)'
    r'|\*\*Parent Epic:\*\*\s*(AE-\d+)'
    r'|\*\*Parent:\*\*\s*(AE-\d+)'
    r'|Parent:\s*(AE-\d+)'
    r'|\*\*Epic:\*\*\s*(AE-\d+)'
    r')',
    re.IGNORECASE | re.MULTILINE,
)

# Also try GH-style patterns (body may not be fully rewritten yet for this issue)
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


def gh_fetch_all() -> dict[int, dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", GH_REPO, "--state", "all",
         "--limit", "1000",
         "--json", "number,title,body,labels,state"],
        capture_output=True, text=True, check=True,
    )
    issues = json.loads(out.stdout)
    return {iss["number"]: iss for iss in issues}


def get_jira_description(client: AtlassianClient, key: str) -> str:
    """Fetch current Jira body as plain text (best effort)."""
    try:
        r = client.jira_get(f"/issue/{key}?fields=description")
        desc = r.get("fields", {}).get("description") or {}
        # Extract text from ADF paragraphs
        parts: list[str] = []

        def walk(node: dict) -> None:
            t = node.get("type", "")
            if t == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                walk(child)

        walk(desc)
        return " ".join(parts)
    except Exception:
        return ""


def find_story_parent_from_jira_body(body_text: str) -> Optional[str]:
    """Look for AE-N parent reference in the cleaned Jira body."""
    m = AE_PARENT_RE.search(body_text)
    if m:
        key = next(g for g in m.groups() if g)
        return key
    return None


def find_story_parent_from_gh_body(
    gh_body: str, issue_map: dict[int, str]
) -> Optional[str]:
    """Fall back to original GitHub body with #N refs."""
    m = GH_PARENT_RE.search(gh_body or "")
    if m:
        n = int(next(g for g in m.groups() if g))
        return issue_map.get(n)
    return None


def is_story(jira_key: str, client: AtlassianClient) -> bool:
    """Check if a Jira key is a Story (not Task/Epic)."""
    try:
        r = client.jira_get(f"/issue/{jira_key}?fields=issuetype")
        itype = r["fields"]["issuetype"]["name"]
        return itype == "Story"
    except Exception:
        return False


def load_done() -> dict:
    if not DONE_FILE.exists():
        return {}
    return json.loads(DONE_FILE.read_text())


def save_done(d: dict) -> None:
    DONE_FILE.write_text(json.dumps(d, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Actually convert Tasks to Subtasks (default is dry-run)")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", type=str, default="",
                        help="Comma-separated Jira keys to process only")
    args = parser.parse_args()
    dry_run = not args.execute

    cfg    = load_config()
    client = AtlassianClient(cfg, requests_per_second=3.0)
    issue_map: dict[int, str] = {
        int(k): v for k, v in json.loads(ISSUE_MAP_FILE.read_text()).items()
    }
    done = load_done()
    only = {k.strip() for k in args.only.split(",") if k.strip()}

    print(f"== Phase 7: Convert Tasks → Subtasks ({'DRY-RUN' if dry_run else 'EXECUTE'}) ==")
    print(f"Already converted: {len(done)}\n")

    print("Fetching GitHub issues for body fallback...")
    gh_issues = gh_fetch_all()
    print(f"  {len(gh_issues)} issues\n")

    # Build task list from issue_map + GitHub labels (no Jira search needed)
    GH_LABEL_TO_TYPE = {
        "type:epic": "Epic", "type:story": "Story",
        "type:task": "Task", "type:bug": "Bug",
    }
    task_keys: list[tuple[int, str]] = []
    for gh_num, jira_key in sorted(issue_map.items()):
        gh = gh_issues.get(gh_num, {})
        if not gh:
            continue
        gh_lbls = [l["name"] for l in gh.get("labels", [])]
        itype = "Task"
        for lbl, tp in GH_LABEL_TO_TYPE.items():
            if lbl in gh_lbls:
                itype = tp
                break
        if itype == "Task":
            task_keys.append((gh_num, jira_key))
    print(f"  Found {len(task_keys)} Task issues (from issue_map)\n")

    processed = errors = 0

    for gh_num, key in task_keys:
        gh = gh_issues.get(gh_num, {})
        summary = (gh.get("title") or key)[:60]

        if only and key not in only:
            continue
        if key in done and not only:
            continue
        if args.limit and processed >= args.limit:
            print(f"\nReached limit ({args.limit}); stopping.")
            break

        # Find the parent Story: try cleaned Jira body first, then GitHub body
        jira_body = get_jira_description(client, key)
        story_key = find_story_parent_from_jira_body(jira_body)

        if not story_key:
            story_key = find_story_parent_from_gh_body(
                gh.get("body", ""), issue_map
            )

        # Validate: parent must be a Story, not an Epic or Task
        if story_key:
            try:
                parent_info = client.jira_get(f"/issue/{story_key}?fields=issuetype")
                parent_type = parent_info["fields"]["issuetype"]["name"]
                if parent_type != "Story":
                    print(f"  {key}  parent {story_key} is a {parent_type}, not Story — skipping parent link")
                    story_key = None
            except Exception:
                story_key = None

        if story_key:
            print(f"  {key}  →  Subtask under {story_key}  [{summary}]")
        else:
            print(f"  {key}  →  stays as Task (no Story parent found)  [{summary}]")

        if dry_run:
            processed += 1
            continue

        # Build payload: change issuetype to Subtask + set parent
        fields: dict = {
            "issuetype": {"name": "Subtask"},
        }
        if story_key:
            fields["parent"] = {"key": story_key}

        r = client.request(
            "PUT", f"{client.cfg.jira_api}/issue/{key}",
            json_body={"fields": fields},
        )

        if r.status_code >= 400:
            err = r.text
            # If Subtask conversion fails (e.g. no subtask in screen), try without issuetype change
            if "issuetype" in err.lower() or "subtask" in err.lower():
                print(f"    ! Subtask conversion failed, trying parent link only")
                fields2: dict = {}
                if story_key:
                    fields2["parent"] = {"key": story_key}
                if fields2:
                    r2 = client.request(
                        "PUT", f"{client.cfg.jira_api}/issue/{key}",
                        json_body={"fields": fields2},
                    )
                    if r2.status_code >= 400:
                        print(f"    !! also failed: {r2.status_code}: {r2.text[:200]}")
                        errors += 1
                        continue
                    else:
                        print(f"    -> parent link set (kept as Task)")
                else:
                    print(f"    !! failed: {r.status_code}: {err[:200]}")
                    errors += 1
                    continue
            else:
                print(f"    !! failed: {r.status_code}: {err[:200]}")
                errors += 1
                continue

        done[key] = {"story": story_key}
        save_done(done)
        processed += 1

    print(f"\n== Done. Processed: {processed}  Errors: {errors}  Total: {len(done)} ==")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
