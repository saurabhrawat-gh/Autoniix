#!/usr/bin/env python3
"""Phase 5: Re-format every migrated Jira issue's description using proper ADF.

Strategy:
  - For each (gh_number, jira_key) in state/issue_map.json:
      1. Fetch original GitHub issue body via `gh`
      2. Convert markdown -> ADF using _md_to_adf
      3. Prepend a small header block (link back to GH original)
      4. PUT updated description on the Jira issue
  - Idempotent: tracks completed in state/beautified.json
  - Resumable: re-running picks up where it stopped
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from _atlassian import AtlassianClient, load_config, get_state_dir
from _md_to_adf import md_to_adf

GH_REPO = "saurabhrawat-gh/Autoniix"
ISSUE_MAP = get_state_dir() / "issue_map.json"
DONE_FILE = get_state_dir() / "beautified.json"


def gh_get(num: int) -> dict:
    out = subprocess.run(
        ["gh", "issue", "view", str(num),
         "--repo", GH_REPO,
         "--json", "number,title,body,url,state,createdAt,closedAt"],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        # Issue may have been deleted or be a PR
        return {}
    return json.loads(out.stdout)


def make_header_adf(gh: dict) -> list[dict]:
    """Small banner: 'Migrated from GitHub #N — link'."""
    url = gh.get("url", f"https://github.com/{GH_REPO}/issues/{gh['number']}")
    return [
        {
            "type": "panel",
            "attrs": {"panelType": "info"},
            "content": [{
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Migrated from GitHub: "},
                    {
                        "type": "text",
                        "text": f"#{gh['number']}",
                        "marks": [{"type": "link", "attrs": {"href": url}}],
                    },
                    {"type": "text", "text": f"  •  Created: {gh.get('createdAt','?')[:10]}"},
                    {"type": "text", "text": f"  •  Closed: {(gh.get('closedAt') or '—')[:10]}"},
                ],
            }],
        },
        {"type": "rule"},
    ]


def load_done() -> dict:
    if not DONE_FILE.exists():
        return {}
    return json.loads(DONE_FILE.read_text())


def save_done(d: dict) -> None:
    DONE_FILE.write_text(json.dumps(d, indent=2))


def update_description(client: AtlassianClient, key: str, doc: dict) -> None:
    body = {"fields": {"description": doc}}
    r = client.request("PUT", f"{client.cfg.jira_api}/issue/{key}", json_body=body)
    if r.status_code >= 400:
        raise RuntimeError(f"PUT {key} -> {r.status_code}: {r.text[:400]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", type=str, default="",
                        help="Run only on specific Jira keys, comma-separated (e.g. AE-29,AE-30)")
    args = parser.parse_args()
    dry_run = not args.execute

    cfg = load_config()
    client = AtlassianClient(cfg)
    issue_map = {int(k): v for k, v in json.loads(ISSUE_MAP.read_text()).items()}
    done = load_done()

    only = {k.strip() for k in args.only.split(",") if k.strip()}

    print(f"== Phase 5: Beautify Jira descriptions  ({'DRY-RUN' if dry_run else 'EXECUTE'}) ==")
    print(f"Issues mapped: {len(issue_map)}  |  Already beautified: {len(done)}\n")

    processed = 0
    for gh_num, jira_key in sorted(issue_map.items()):
        if only and jira_key not in only:
            continue
        if jira_key in done and not only:
            continue
        if args.limit and processed >= args.limit:
            print(f"\nReached limit ({args.limit}); stopping.")
            break

        gh = gh_get(gh_num)
        if not gh:
            print(f"  ! GH#{gh_num} unreachable; skipping {jira_key}")
            continue

        body = gh.get("body") or ""
        try:
            content_adf = md_to_adf(body)
        except Exception as e:
            print(f"  !! md->adf failed for GH#{gh_num} ({jira_key}): {e}")
            continue

        # Prepend header banner
        full_doc = {
            "type": "doc",
            "version": 1,
            "content": make_header_adf(gh) + content_adf["content"],
        }

        print(f"  {jira_key}  <-  GH#{gh_num}  ({len(body)} chars body)")
        if dry_run:
            continue

        try:
            update_description(client, jira_key, full_doc)
            done[jira_key] = gh_num
            save_done(done)
            processed += 1
        except RuntimeError as e:
            err = str(e)
            print(f"     !! update failed: {err[:200]}")
            # Fallback: reduce to plain paragraphs (some unsupported ADF construct)
            try:
                fallback_doc = md_to_adf("```\n" + body[:30000] + "\n```")
                update_description(client, jira_key, {
                    "type": "doc", "version": 1,
                    "content": make_header_adf(gh) + fallback_doc["content"],
                })
                done[jira_key] = gh_num
                save_done(done)
                processed += 1
                print(f"     -> fallback succeeded (raw code block)")
            except RuntimeError as e2:
                print(f"     !! fallback also failed: {str(e2)[:200]}")

    print(f"\n== Done. Beautified this run: {processed}.  Total done: {len(done)} / {len(issue_map)} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
