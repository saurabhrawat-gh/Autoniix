#!/usr/bin/env python3
"""Phase 6: Fix hierarchy, rewrite bodies, remove labels, fill custom fields.

What this script does for EVERY issue in issue_map.json:
  1. Set the correct Jira parent link  (Story → Epic, Task → Story)
  2. Rewrite the description body:
       - Strip the "Migrated from GitHub" migration header
       - Replace all  #N  GitHub refs with  AE-X  Jira refs
  3. Update the summary (title) to replace #N with AE-X refs
  4. Clear all labels  (replace with empty array)
  5. Fill custom fields:
       - customfield_10074 (Severity)  from priority-* label
       - customfield_10075 (Layer)     from domain/type label
       - customfield_10073 (Environment) from status label or context

Idempotent: progress tracked in state/fixed.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests

from _atlassian import AtlassianClient, load_config, get_state_dir
from _md_to_adf import md_to_adf

GH_REPO       = "saurabhrawat-gh/Autoniix"
ISSUE_MAP_FILE = get_state_dir() / "issue_map.json"
DONE_FILE      = get_state_dir() / "fixed.json"

# Match #N that is NOT already part of an AE-N pattern, TC-N, or similar
GH_REF_RE = re.compile(r'(?<![A-Za-z0-9_\-])#(\d+)(?![A-Za-z0-9_])')

# Strip the "Migrated from GitHub" banner that script 05 prepended
MIGRATION_BANNER_RE = re.compile(
    r'Migrated from GitHub:\s*\[?#?\d+\]?\s*(?:\([^\)]*\))?\s*[•\-]\s*Created:[^\n]*\n?'
    r'(?:\s*[•\-]?\s*Closed:[^\n]*\n?)?'
    r'(?:\s*Original number:[^\n]*\n?)?',
    re.IGNORECASE,
)
MIGRATION_HEADER_BLOCK_RE = re.compile(
    r'^Migrated from GitHub:.*?(?=\n## |\n# |\Z)',
    re.MULTILINE | re.DOTALL,
)

# Map domain labels to Jira Layer field options
LABEL_TO_LAYER: dict[str, str] = {
    "auth":         "Auth",
    "workspace":    "Service",
    "providers":    "Service",
    "provider":     "Service",
    "deployment":   "Infra",
    "infra":        "Infra",
    "test-plan":    "Test",
    "test-case":    "Test",
    "test":         "Test",
    "process":      "Infra",
    "worker":       "Worker",
    "db":           "DB",
    "database":     "DB",
    "gateway":      "Gateway",
    "ui":           "UI",
    "dashboard":    "UI",
    "analytics":    "Service",
    "intelligence": "Service",
}

LABEL_TO_SEVERITY: dict[str, str] = {
    "priority-critical": "Critical",
    "priority-high":     "High",
    "priority-medium":   "Medium",
    "priority-low":      "Low",
}

LABEL_TO_ENV: dict[str, str] = {
    "in-qa":        "QA",
    "qa-verified":  "QA",
    "in-prod":      "Production",
    "prod-verified":"Production",
    "ready-to-deploy": "Production",
}

# Skip tickets we don't want to auto-set environment for (epics, process, infra)
NO_ENV_TYPES = {"Epic"}

GH_LABEL_TO_TYPE: dict[str, str] = {
    "type:epic":  "Epic",
    "type:story": "Story",
    "type:task":  "Task",
    "type:bug":   "Bug",
}


def gh_fetch_all() -> dict[int, dict]:
    out = subprocess.run(
        ["gh", "issue", "list",
         "--repo", GH_REPO,
         "--state", "all",
         "--limit", "1000",
         "--json", "number,title,body,labels,state,createdAt,closedAt"],
        capture_output=True, text=True, check=True,
    )
    issues = json.loads(out.stdout)
    return {iss["number"]: iss for iss in issues}


def parent_gh_number(body: str) -> Optional[int]:
    """Extract closest parent GitHub issue number from body.

    Priority order:
      1. Explicit 'Parent Story: #N' or 'Tests for Story: #N'  (task → story)
      2. 'Parent Epic: #N'                                      (story → epic)
      3. Generic 'Parent: #N'
      4. Bare 'Epic: #N'  (last resort)
    """
    if not body:
        return None
    # Ordered from most specific to least specific
    patterns = [
        r"\*\*Parent Story:\*\*\s*#(\d+)",          # **Parent Story:** #N
        r"\*\*Tests for Story:\*\*\s*#(\d+)",        # **Tests for Story:** #N
        r"Tests for Story:\s*#(\d+)",                # Tests for Story: #N
        r"Tests for:\s*#(\d+)",                      # Tests for: #N
        r"Parent Story:\s*#(\d+)",                   # Parent Story: #N
        r"\*\*Parent Epic:\*\*\s*#(\d+)",            # **Parent Epic:** #N
        r"Parent Epic:\s*#(\d+)",                    # Parent Epic: #N
        r"\*\*Parent:\*\*\s*#(\d+)",                 # **Parent:** #N
        r"Parent:\s*#(\d+)",                         # Parent: #N
        r"\*\*Epic:\*\*\s*#(\d+)",                   # **Epic:** #N
        r"(?:^|\s)Epic:\s*#(\d+)(?:\s|$)",          # bare Epic: #N
    ]
    for p in patterns:
        m = re.search(p, body, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return int(m.group(1))
    return None


def replace_gh_refs(text: str, issue_map: dict[int, str]) -> str:
    def _rep(m: re.Match) -> str:
        n = int(m.group(1))
        return issue_map[n] if n in issue_map else m.group(0)
    return GH_REF_RE.sub(_rep, text)


def strip_migration_header(body: str) -> str:
    # Remove the full "Migrated from GitHub: ..." header block up to the first ---
    body = re.sub(
        r'^Migrated from GitHub:.*?\n(?:.*?\n)*?---\s*\n',
        '', body, count=1, flags=re.MULTILINE,
    )
    # Catch single-line variant (05_beautify sometimes leaves it in the ADF panel already, but
    # this runs on the RAW github body, so it won't be there in ADF form)
    body = re.sub(r'^Migrated from GitHub:\s*\[#\d+\]\([^\)]+\)[^\n]*\n?', '', body, flags=re.MULTILINE)
    body = re.sub(r'^Original number:\s*#\d+\s*\n?', '', body, flags=re.MULTILINE)
    body = re.sub(r'^Created:\s*\S+\s*\|\s*Closed:\s*\S+\s*\n?', '', body, flags=re.MULTILINE)
    # strip any leftover leading ---
    body = re.sub(r'^\s*---\s*\n', '', body)
    return body.strip()


def clean_body(raw_body: str, issue_map: dict[int, str]) -> str:
    body = strip_migration_header(raw_body)
    body = replace_gh_refs(body, issue_map)
    return body


def clean_summary(title: str, issue_map: dict[int, str]) -> str:
    # Replace any leading #N refs in title
    title = replace_gh_refs(title, issue_map)
    # Strip leading [Type] prefix if present (already cleaned by script 03 but just in case)
    title = re.sub(r'^\[(Epic|Story|Task|Bug|Feature|task|story|epic|bug)\]\s*', '', title, flags=re.IGNORECASE)
    return title.strip()[:240]


def infer_layer(labels: list[str]) -> Optional[str]:
    for lbl in labels:
        if lbl in LABEL_TO_LAYER:
            return LABEL_TO_LAYER[lbl]
    return None


def infer_severity(labels: list[str]) -> Optional[str]:
    for lbl in labels:
        if lbl in LABEL_TO_SEVERITY:
            return LABEL_TO_SEVERITY[lbl]
    return None


def infer_env(labels: list[str]) -> Optional[str]:
    for lbl in labels:
        if lbl in LABEL_TO_ENV:
            return LABEL_TO_ENV[lbl]
    return None


def fetch_field_options(client: AtlassianClient, field_id: str) -> list[str]:
    """Fetch valid options for a custom select field."""
    try:
        r = client.request("GET", f"{client.cfg.jira_api}/field/{field_id}/context/option")
        if r.status_code == 200:
            data = r.json()
            return [o["value"] for o in data.get("values", [])]
    except Exception:
        pass
    return []


def get_custom_field_contexts(client: AtlassianClient) -> dict[str, list[str]]:
    """Get all option values for our three custom fields."""
    fields = {
        "customfield_10073": [],  # Environment
        "customfield_10074": [],  # Severity
        "customfield_10075": [],  # Layer
    }
    for fid in fields:
        opts = fetch_field_options(client, fid)
        if opts:
            fields[fid] = opts
            print(f"  Field {fid} options: {opts}")
        else:
            # Fallback: known values from field setup
            if fid == "customfield_10073":
                fields[fid] = ["QA", "Production", "Local"]
            elif fid == "customfield_10074":
                fields[fid] = ["Critical", "High", "Medium", "Low"]
            elif fid == "customfield_10075":
                fields[fid] = ["UI", "Gateway", "Service", "DB", "Auth", "Worker", "Infra", "Test"]
            print(f"  Field {fid}: using fallback options {fields[fid]}")
    return fields


def build_custom_fields(
    gh_labels: list[str],
    issue_type: str,
    field_options: dict[str, list[str]],
) -> dict:
    """Build additional_fields dict for custom fields."""
    extra: dict = {}

    severity = infer_severity(gh_labels)
    if severity and severity in field_options.get("customfield_10074", []):
        extra["customfield_10074"] = {"value": severity}

    layer = infer_layer(gh_labels)
    if layer and layer in field_options.get("customfield_10075", []):
        extra["customfield_10075"] = {"value": layer}

    if issue_type not in NO_ENV_TYPES:
        env = infer_env(gh_labels)
        if env and env in field_options.get("customfield_10073", []):
            extra["customfield_10073"] = {"value": env}

    return extra


def find_grandparent_epic(
    body: str,
    gh_issues: dict[int, dict],
    issue_map: dict[int, str],
) -> Optional[str]:
    """For a Task whose direct parent is a Story: find the Story's Epic key."""
    story_gh = parent_gh_number(body)
    if not story_gh or story_gh not in gh_issues:
        return None
    story_body = gh_issues[story_gh].get("body", "") or ""
    epic_gh = parent_gh_number(story_body)
    if epic_gh:
        return issue_map.get(epic_gh)
    return None


def update_issue(
    client: AtlassianClient,
    jira_key: str,
    parent_key: Optional[str],
    gh: dict,
    issue_map: dict[int, str],
    issue_type: str,
    field_options: dict[str, list[str]],
    dry_run: bool,
    gh_issues: Optional[dict] = None,
) -> bool:
    raw_body  = gh.get("body") or ""
    gh_labels = [l["name"] for l in gh.get("labels", [])]
    gh_title  = gh.get("title", "")

    cleaned_body    = clean_body(raw_body, issue_map)
    cleaned_summary = clean_summary(gh_title, issue_map)

    try:
        adf = md_to_adf(cleaned_body if cleaned_body else "(no content)")
    except Exception as e:
        print(f"    ! md->adf failed for {jira_key}: {e}")
        adf = {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": cleaned_body[:30000] or "(no content)"}]}
        ]}

    fields: dict = {
        "summary":     cleaned_summary,
        "description": adf,
        "labels":      [],
    }

    if parent_key:
        fields["parent"] = {"key": parent_key}

    # Merge custom fields
    custom = build_custom_fields(gh_labels, issue_type, field_options)
    fields.update(custom)

    if dry_run:
        parent_str = f" → parent: {parent_key}" if parent_key else ""
        extras = list(custom.keys())
        print(f"  [DRY] {jira_key}{parent_str}  body={len(cleaned_body)}c  extras={extras}")
        return True

    def _put(f: dict) -> requests.Response:
        return client.request("PUT", f"{client.cfg.jira_api}/issue/{jira_key}",
                              json_body={"fields": f})

    r = _put(fields)

    if r.status_code >= 400:
        err = r.text.lower()

        # 1. Custom fields not on screen → strip them and retry
        if "customfield" in err and "screen" in err:
            print(f"    ! custom fields not on screen, retrying without them")
            fields = {k: v for k, v in fields.items() if not k.startswith("customfield_")}
            r = _put(fields)

        # 2. Parent link rejected → try grandparent Epic, then give up on parent
        if r.status_code >= 400 and parent_key and "parent" in r.text.lower():
            raw_body = gh.get("body") or ""
            grandparent = (
                find_grandparent_epic(raw_body, gh_issues, issue_map)
                if gh_issues else None
            )
            if grandparent and grandparent != parent_key:
                print(f"    ! parent link rejected, trying grandparent Epic: {grandparent}")
                fields["parent"] = {"key": grandparent}
                r = _put(fields)
            if r.status_code >= 400:
                print(f"    ! parent link rejected ({r.status_code}), retrying without parent")
                fields = {k: v for k, v in fields.items() if k != "parent"}
                r = _put(fields)

        if r.status_code >= 400:
            print(f"    !! failed: {r.status_code}: {r.text[:300]}")
            return False

    return True


def load_done() -> dict:
    if not DONE_FILE.exists():
        return {}
    return json.loads(DONE_FILE.read_text())


def save_done(d: dict) -> None:
    DONE_FILE.write_text(json.dumps(d, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Actually update Jira issues (default is dry-run)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after N updates (0 = no limit)")
    parser.add_argument("--only", type=str, default="",
                        help="Run only on specific Jira keys, comma-separated (e.g. AE-6,AE-7)")
    args = parser.parse_args()
    dry_run = not args.execute

    cfg    = load_config()
    client = AtlassianClient(cfg, requests_per_second=3.0)
    issue_map_raw = json.loads(ISSUE_MAP_FILE.read_text())
    issue_map: dict[int, str] = {int(k): v for k, v in issue_map_raw.items()}
    done = load_done()

    only = {k.strip() for k in args.only.split(",") if k.strip()}

    print(f"== Phase 6: Fix Hierarchy + Labels + Bodies ({'DRY-RUN' if dry_run else 'EXECUTE'}) ==")
    print(f"Mapped issues: {len(issue_map)}  |  Already fixed: {len(done)}\n")

    print("Fetching custom field options...")
    field_options = get_custom_field_contexts(client)
    print()

    print("Fetching all GitHub issues...")
    gh_issues = gh_fetch_all()
    print(f"  Fetched {len(gh_issues)} GitHub issues\n")

    # Build issue-type map from GitHub labels (no extra API calls needed)
    jira_types: dict[str, str] = {}
    for gh_num_str, jira_k in issue_map_raw.items():
        gh = gh_issues.get(int(gh_num_str))
        if not gh:
            continue
        gh_lbls = [l["name"] for l in gh.get("labels", [])]
        t = "Task"
        for lbl, tp in GH_LABEL_TO_TYPE.items():
            if lbl in gh_lbls:
                t = tp
                break
        jira_types[jira_k] = t
    print(f"  Inferred types for {len(jira_types)} issues\n")

    processed = 0
    errors = 0

    for gh_num, jira_key in sorted(issue_map.items()):
        if only and jira_key not in only:
            continue
        if jira_key in done and not only:
            continue
        if args.limit and processed >= args.limit:
            print(f"\nReached limit ({args.limit}); stopping.")
            break

        gh = gh_issues.get(gh_num)
        if not gh:
            print(f"  ! GH#{gh_num} ({jira_key}): not in GitHub data — skipping")
            continue

        body = gh.get("body") or ""
        parent_gh = parent_gh_number(body)
        parent_key = issue_map.get(parent_gh) if parent_gh else None
        issue_type = jira_types.get(jira_key, "Task")

        parent_str = f" → {parent_key}" if parent_key else ""
        print(f"  {jira_key} (GH#{gh_num}, {issue_type}){parent_str}")

        ok = update_issue(
            client, jira_key, parent_key, gh, issue_map,
            issue_type, field_options, dry_run,
            gh_issues=gh_issues,
        )

        if ok:
            if not dry_run:
                done[jira_key] = {"gh": gh_num, "parent": parent_key, "type": issue_type}
                save_done(done)
            processed += 1
        else:
            errors += 1

    print(f"\n== Done. Processed: {processed}  Errors: {errors}  Total fixed: {len(done)}/{len(issue_map)} ==")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
