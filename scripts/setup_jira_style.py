#!/usr/bin/env python3
"""
Jira-style GitHub Issues setup for Autoniix (saurabhrawat-gh/Autoniix).

What this script does:
  1. Creates/updates five type labels with distinct colors
  2. Prefixes every issue title with [ATNX-{number}]
  3. Adds the correct type:* label to every issue (based on existing labels)

Usage:
    GITHUB_TOKEN=ghp_xxxx python3 scripts/setup_jira_style.py
    GITHUB_TOKEN=ghp_xxxx python3 scripts/setup_jira_style.py --dry-run
"""

import os
import sys
import time
from urllib.parse import quote
import requests

# ── Config ────────────────────────────────────────────────────────────────────────────
OWNER    = "saurabhrawat-gh"
REPO     = "Autoniix"
PREFIX   = "ATNX"
BASE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable is not set.")
    print("       Export it first:  export GITHUB_TOKEN=ghp_xxxx")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Label Definitions ───────────────────────────────────────────────────────────────────────
TYPE_LABELS = [
    {
        "name": "type:epic",
        "color": "7C3AED",
        "description": "Large feature container — spans multiple stories",
    },
    {
        "name": "type:story",
        "color": "2563EB",
        "description": "User story — a deliverable slice of user value",
    },
    {
        "name": "type:task",
        "color": "059669",
        "description": "Implementation task, test plan, or operational work item",
    },
    {
        "name": "type:subtask",
        "color": "34D399",
        "description": "Sub-task nested under a story or task",
    },
    {
        "name": "type:bug",
        "color": "DC2626",
        "description": "Defect — something is broken or behaves incorrectly",
    },
]


# ── Helpers ─────────────────────────────────────────────────────────────────────────────

def _get(path, **params):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def _post(path, data):
    r = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=data)
    return r


def _patch(path, data):
    r = requests.patch(f"{BASE_URL}{path}", headers=HEADERS, json=data)
    return r


# ── Step 1: Labels ──────────────────────────────────────────────────────────────────────────────

def ensure_labels():
    print("── STEP 1: Type Labels ────────────────────────────────────────────────")
    for lbl in TYPE_LABELS:
        encoded = quote(lbl["name"], safe="")
        r = requests.get(f"{BASE_URL}/labels/{encoded}", headers=HEADERS)
        if r.status_code == 404:
            r2 = _post("/labels", lbl)
            if r2.status_code == 201:
                print(f"  ✅  Created  [{lbl['name']}]  #{lbl['color']}")
            else:
                print(f"  ❌  Failed to create [{lbl['name']}]: {r2.text[:120]}")
        elif r.status_code == 200:
            existing = r.json()
            needs_update = (
                existing["color"].lower() != lbl["color"].lower()
                or existing.get("description", "") != lbl["description"]
            )
            if needs_update:
                r2 = requests.patch(
                    f"{BASE_URL}/labels/{encoded}", headers=HEADERS, json=lbl
                )
                print(
                    f"  🔄  Updated  [{lbl['name']}]"
                    if r2.status_code == 200
                    else f"  ❌  Failed to update [{lbl['name']}]: {r2.text[:120]}"
                )
            else:
                print(f"  ✓   Exists   [{lbl['name']}]  (no change)")
        else:
            print(f"  ⚠️   Unexpected status {r.status_code} for [{lbl['name']}]")
        time.sleep(0.1)


# ── Step 2 & 3: Issues ────────────────────────────────────────────────────────────────────────────

def infer_type_label(label_names: set) -> str:
    """Return the correct type:* label given an issue's current label set."""
    if "epic" in label_names:
        return "type:epic"
    if "bug" in label_names:
        return "type:bug"
    if "subtask" in label_names or "sub-task" in label_names:
        return "type:subtask"
    if "story" in label_names:
        return "type:story"
    return "type:task"   # test-plan, deployment, task, etc.


def fetch_all_issues() -> list:
    """Fetch ALL issues (open + closed), excluding pull requests."""
    all_issues = []
    page = 1
    while True:
        batch = _get("/issues", state="all", per_page=100, page=page)
        batch = [i for i in batch if "pull_request" not in i]
        if not batch:
            break
        all_issues.extend(batch)
        page += 1
        time.sleep(0.2)
    return all_issues


def process_issues(issues: list, dry_run: bool):
    print(f"\n── STEP 2 & 3: Titles + Type Labels  ({len(issues)} issues) ─────────────────")
    updated = skipped = errors = 0

    for issue in issues:
        num    = issue["number"]
        title  = issue["title"]
        labels = issue["labels"]
        label_names = {l["name"] for l in labels}

        # ── Title ──
        prefix_tag = f"[{PREFIX}-{num}]"
        if title.startswith(prefix_tag):
            new_title = title
        else:
            new_title = f"{prefix_tag} {title}"

        # ── Type label ──
        type_label = infer_type_label(label_names)
        already_has_type = type_label in label_names

        title_changed = new_title != title
        labels_changed = not already_has_type

        if not title_changed and not labels_changed:
            print(f"  ✓   #{num:>3}  (no changes)")
            skipped += 1
            continue

        if dry_run:
            parts = []
            if title_changed:
                parts.append(f"title → '{new_title[:60]}'")
            if labels_changed:
                parts.append(f"+{type_label}")
            print(f"  DRY #{num:>3}  {' | '.join(parts)}")
            skipped += 1
            continue

        payload = {}
        if title_changed:
            payload["title"] = new_title
        if labels_changed:
            payload["labels"] = list(label_names) + [type_label]

        r = _patch(f"/issues/{num}", payload)
        if r.status_code == 200:
            parts = []
            if title_changed:
                parts.append("title")
            if labels_changed:
                parts.append(f"+{type_label}")
            print(f"  ✅  #{num:>3}  {', '.join(parts)}")
            updated += 1
        else:
            print(f"  ❌  #{num:>3}  HTTP {r.status_code}: {r.text[:120]}")
            errors += 1

        time.sleep(0.25)

    return updated, skipped, errors


# ── Filter Reference ──────────────────────────────────────────────────────────────────────────────

def print_filters():
    base = f"https://github.com/{OWNER}/{REPO}/issues"
    print("\n── SAVED FILTER LINKS ────────────────────────────────────────────────")
    rows = [
        ("Epics",    "type:epic"),
        ("Stories",  "type:story"),
        ("Tasks",    "type:task"),
        ("Subtasks", "type:subtask"),
        ("Bugs",     "type:bug"),
    ]
    for name, lbl in rows:
        print(f"  {name:<10} {base}?q=is%3Aopen+label%3A{quote(lbl, safe='')}")


# ── Main ──────────────────────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("🔍  DRY RUN — reading only, no writes\n")

    ensure_labels()

    print("\n── Fetching all issues … ────────────────────────────────────────────────")
    issues = fetch_all_issues()
    print(f"  Found {len(issues)} issues (open + closed, PRs excluded)")

    updated, skipped, errors = process_issues(issues, dry_run)

    print("\n── SUMMARY ────────────────────────────────────────────────────────────────────────────")
    if dry_run:
        needs_update = sum(1 for i in issues if not i["title"].startswith(f"[{PREFIX}-{i['number']}]"))
        print(f"  Would update : {needs_update}")
    else:
        print(f"  Updated  : {updated}")
        print(f"  Skipped  : {skipped}  (already correct)")
        print(f"  Errors   : {errors}")

    print_filters()
    print()


if __name__ == "__main__":
    main()
