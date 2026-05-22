#!/usr/bin/env python3
"""Phase 3: Migrate GitHub issues -> Jira project AE.

Strategy:
  1. Fetch all GitHub issues (PRs auto-excluded by `gh issue list`)
  2. Group: Epics first, then Stories, then Tasks/Bugs/untyped
  3. For each issue:
       - Skip if already migrated (state/issue_map.json)
       - Create Jira issue with type, summary (cleaned), description (preserved + GH link)
       - Set parent link if "Parent Story: #N" or "Epic: #N" found in body
       - Transition to appropriate status from labels / state
       - Apply labels for traceability (`gh-{N}`)
  4. Resumable: re-running picks up where it left off

Run modes:
  --dry-run   Print plan, write 0 issues to Jira (default)
  --execute   Actually create Jira issues

Idempotent: safe to re-run; uses state/issue_map.json
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

JIRA_PROJECT_KEY = "AE"
GH_REPO = "saurabhrawat-gh/Autoniix"

STATE_FILE = get_state_dir() / "issue_map.json"

# Label → Jira issue type
TYPE_MAP = {
    "type:epic":  "Epic",
    "type:story": "Story",
    "type:task":  "Task",
    "type:bug":   "Bug",
}
DEFAULT_TYPE = "Task"

# Label → Jira status (ordered by lifecycle)
STATUS_MAP = {
    "ready-for-dev":   "To Do",
    "in-progress":     "In Progress",
    "in-qa":           "In QA",
    "qa-verified":     "QA Verified",
    "ready-to-deploy": "Ready to Deploy",
    "in-prod":         "In Prod",
    "prod-verified":   "Prod Verified",
}

# Migration order — must match Jira parent-link constraints
TYPE_ORDER = ["Epic", "Story", "Task", "Bug"]


def gh_fetch_all() -> list[dict]:
    """Fetch every open + closed issue (excludes PRs automatically)."""
    out = subprocess.run(
        ["gh", "issue", "list",
         "--repo", GH_REPO,
         "--state", "all",
         "--limit", "1000",
         "--json", "number,title,body,labels,state,milestone,createdAt,closedAt,assignees"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def load_state() -> dict[int, str]:
    if not STATE_FILE.exists():
        return {}
    return {int(k): v for k, v in json.loads(STATE_FILE.read_text()).items()}


def save_state(state: dict[int, str]) -> None:
    STATE_FILE.write_text(json.dumps({str(k): v for k, v in state.items()}, indent=2))


def issue_type(labels: list[str]) -> str:
    for lbl in labels:
        if lbl in TYPE_MAP:
            return TYPE_MAP[lbl]
    return DEFAULT_TYPE


def issue_status(labels: list[str], state: str) -> str:
    if state == "CLOSED":
        return "Done"
    for lbl in labels:
        if lbl in STATUS_MAP:
            return STATUS_MAP[lbl]
    return "To Do"


def clean_summary(title: str) -> str:
    """Strip `[Type] ` prefix; max 240 chars (Jira limit ~255)."""
    cleaned = re.sub(r"^\[(Epic|Story|Task|Bug|Feature|task|story|epic|bug)\]\s*", "", title, flags=re.IGNORECASE)
    return cleaned[:240]


def parent_gh_number(body: str) -> Optional[int]:
    """Extract first 'Parent Story: #N' or 'Parent: #N' or 'Epic: #N' reference."""
    if not body:
        return None
    patterns = [
        r"\*\*Parent Story:\*\*\s*#(\d+)",
        r"\*\*Parent:\*\*\s*#(\d+)",
        r"Parent Story:\s*#(\d+)",
        r"Parent:\s*#(\d+)",
        r"\*\*Epic:\*\*\s*#(\d+)",
        r"Epic:\s*#(\d+)\s",
    ]
    for p in patterns:
        m = re.search(p, body, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return int(m.group(1))
    return None


def adf_from_text(text: str) -> dict:
    """Wrap plain text into a minimal ADF doc that Jira API v3 accepts."""
    text = text or ""
    paragraphs = text.split("\n\n")
    content = []
    for p in paragraphs:
        if not p.strip():
            continue
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": p[:30000]}]
        })
    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": "(no body)"}]}]
    return {"type": "doc", "version": 1, "content": content}


def build_description(gh: dict) -> dict:
    body = gh.get("body") or ""
    header = (
        f"Migrated from GitHub: https://github.com/{GH_REPO}/issues/{gh['number']}\n"
        f"Original number: #{gh['number']}\n"
        f"Created: {gh.get('createdAt','?')}  |  Closed: {gh.get('closedAt') or '—'}\n\n"
        "---\n\n"
    )
    return adf_from_text(header + body)


def transition_to(client: AtlassianClient, key: str, target_status: str) -> None:
    if target_status == "To Do":
        return  # default state, no-op
    transitions = client.jira_get(f"/issue/{key}/transitions")
    tid = next(
        (t["id"] for t in transitions.get("transitions", [])
         if t["to"]["name"] == target_status),
        None,
    )
    if not tid:
        print(f"    ! cannot transition {key} -> {target_status} (not available)")
        return
    client.jira_post(f"/issue/{key}/transitions", {"transition": {"id": tid}})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Actually create Jira issues. Without this, runs dry.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after N migrations (0 = no limit). Useful for testing.")
    args = parser.parse_args()
    dry_run = not args.execute

    cfg = load_config()
    client = AtlassianClient(cfg)
    state = load_state()

    print("== Phase 3: Migrate GitHub Issues -> Jira ==\n")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print(f"Already migrated: {len(state)} issues\n")

    print("Fetching GitHub issues...")
    gh_issues = gh_fetch_all()
    print(f"  total: {len(gh_issues)}\n")

    # Sort by type order, then by gh number ascending (parents before children)
    def sort_key(gh):
        labels = [l["name"] for l in gh.get("labels", [])]
        t = issue_type(labels)
        return (TYPE_ORDER.index(t) if t in TYPE_ORDER else 99, gh["number"])

    gh_issues.sort(key=sort_key)

    # Show plan summary
    from collections import Counter
    plan = Counter()
    for g in gh_issues:
        labels = [l["name"] for l in g.get("labels", [])]
        plan[issue_type(labels)] += 1
    print(f"Plan: {dict(plan)}\n")

    migrated_this_run = 0
    for gh in gh_issues:
        n = gh["number"]
        if n in state:
            continue
        if args.limit and migrated_this_run >= args.limit:
            print(f"\nReached limit ({args.limit}); stopping.")
            break

        labels = [l["name"] for l in gh.get("labels", [])]
        itype = issue_type(labels)
        status = issue_status(labels, gh["state"])
        summary = clean_summary(gh["title"])
        parent_n = parent_gh_number(gh.get("body") or "")

        print(f"[#{n}] {itype:<5} -> {status:<15} | {summary[:60]}")
        if parent_n:
            parent_jira = state.get(parent_n)
            print(f"      parent: GH #{parent_n}{' (= ' + parent_jira + ')' if parent_jira else ' (NOT YET MIGRATED)'}")

        if dry_run:
            continue

        # Build payload
        # Jira labels: prefix with `gh-` for traceability + add original GH labels (sanitised)
        jira_labels = [f"gh-{n}"]
        for lbl in labels:
            if lbl.startswith(("type:", "status:")):
                continue
            jira_labels.append(lbl.replace(" ", "-").replace(":", "-")[:50])

        payload: dict = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "issuetype": {"name": itype},
                "summary": summary,
                "description": build_description(gh),
                "labels": jira_labels,
            }
        }
        # Parent linking — only valid for sub-tasks in standard Jira; for team-managed
        # next-gen we use the `parent` field on Stories/Tasks pointing at Epics.
        if parent_n and parent_n in state:
            payload["fields"]["parent"] = {"key": state[parent_n]}

        try:
            r = client.jira_post("/issue", payload)
            jira_key = r["key"]
            state[n] = jira_key
            save_state(state)
            print(f"      -> created {jira_key}")
        except RuntimeError as e:
            # If parent linking fails, retry without parent
            msg = str(e)
            if "parent" in msg.lower() and "parent" in payload["fields"]:
                print(f"      ! parent link failed, retrying without parent: {msg[:120]}")
                payload["fields"].pop("parent")
                try:
                    r = client.jira_post("/issue", payload)
                    jira_key = r["key"]
                    state[n] = jira_key
                    save_state(state)
                    print(f"      -> created {jira_key} (no parent link)")
                except RuntimeError as e2:
                    print(f"      !! still failed: {e2}")
                    continue
            else:
                print(f"      !! create failed: {e}")
                continue

        # Transition to target status
        try:
            transition_to(client, jira_key, status)
        except RuntimeError as e:
            print(f"      ! transition failed: {e}")

        migrated_this_run += 1

    print(f"\n== Done. Migrated this run: {migrated_this_run}. Total: {len(state)} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
