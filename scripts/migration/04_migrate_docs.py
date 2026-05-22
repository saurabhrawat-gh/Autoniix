#!/usr/bin/env python3
"""Phase 4: Migrate docs/*.md from repo -> Confluence space ATNX (Autoniix Engineering).

Strategy:
  - Walk docs/ recursively
  - Top-level files become children of the space homepage
  - Subfolders become parent pages (one per folder), files inside become their children
  - Markdown is converted to HTML, then submitted as Confluence "storage" format
  - State file maps relative path -> Confluence page id (idempotent / resumable)

Run modes:
  --dry-run   Print plan only (default)
  --execute   Actually create Confluence pages
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import markdown as md

from _atlassian import AtlassianClient, load_config, get_state_dir

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
SPACE_ID = "491524"            # Autoniix Engineering (key=ATNX)
SPACE_HOMEPAGE = "491697"
SPACE_KEY = "ATNX"

STATE_FILE = get_state_dir() / "docs_map.json"

EXCLUDE = {"migration"}  # don't push our own migration spec back into Confluence


def load_state() -> dict[str, dict]:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict[str, dict]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def md_to_html(text: str) -> str:
    """Convert markdown to HTML suitable for Confluence storage format."""
    html = md.markdown(
        text,
        extensions=["fenced_code", "tables", "toc", "sane_lists", "nl2br"],
    )
    # Strip raw <script> just in case
    html = re.sub(r"<script.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    return html


def title_from(path: Path) -> str:
    """Use first `# Heading` if found, else filename without extension."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()[:240]
    return path.stem.replace("-", " ").replace("_", " ").title()[:240]


def create_page(client: AtlassianClient, title: str, html: str, parent_id: str) -> str:
    body = {
        "spaceId": SPACE_ID,
        "status": "current",
        "title": title,
        "parentId": parent_id,
        "body": {
            "representation": "storage",
            "value": html,
        },
    }
    resp = client.confluence_post("/pages", body)
    return resp["id"]


def create_folder_page(client: AtlassianClient, name: str, parent_id: str) -> str:
    """Create an empty parent page for a folder."""
    title = name.replace("-", " ").replace("_", " ").title()[:240]
    intro = f"<p>This page groups documents from the <strong>{name}/</strong> folder of the repository.</p>"
    body = {
        "spaceId": SPACE_ID,
        "status": "current",
        "title": title,
        "parentId": parent_id,
        "body": {"representation": "storage", "value": intro},
    }
    resp = client.confluence_post("/pages", body)
    return resp["id"]


def collect_docs() -> list[tuple[Path, list[str]]]:
    """Return list of (file_path, [folder_segments_relative_to_docs])."""
    out = []
    for p in sorted(DOCS_DIR.rglob("*.md")):
        rel = p.relative_to(DOCS_DIR)
        if rel.parts[0] in EXCLUDE:
            continue
        out.append((p, list(rel.parts[:-1])))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    dry_run = not args.execute

    cfg = load_config()
    client = AtlassianClient(cfg)
    state = load_state()

    print("== Phase 4: Migrate docs -> Confluence (space ATNX) ==\n")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print(f"Already migrated pages: {len(state)}\n")

    docs = collect_docs()
    print(f"Total markdown files (excluding {EXCLUDE}): {len(docs)}\n")

    folder_ids: dict[str, str] = {"": SPACE_HOMEPAGE}
    # Pre-fill folder_ids from state
    for path_key, info in state.items():
        if info.get("kind") == "folder":
            folder_ids[path_key] = info["id"]

    migrated_this_run = 0
    for path, folders in docs:
        rel_str = str(path.relative_to(DOCS_DIR))
        if rel_str in state:
            continue
        if args.limit and migrated_this_run >= args.limit:
            print(f"\nReached limit ({args.limit}); stopping.")
            break

        # Ensure folder pages exist (one per folder segment)
        cur = ""
        parent_id = SPACE_HOMEPAGE
        for seg in folders:
            cur = f"{cur}/{seg}" if cur else seg
            if cur not in folder_ids:
                print(f"  + folder page: {cur}")
                if not dry_run:
                    fid = create_folder_page(client, seg, parent_id)
                    folder_ids[cur] = fid
                    state[cur] = {"kind": "folder", "id": fid}
                    save_state(state)
                else:
                    folder_ids[cur] = "DRY"
            parent_id = folder_ids[cur]

        title = title_from(path)
        # Disambiguate: if title clashes with an already-migrated page, append filename
        existing_titles = {info.get("title") for info in state.values() if info.get("kind") == "page"}
        if title in existing_titles:
            title = f"{title} ({path.stem})"[:240]

        print(f"  {rel_str}  ->  '{title}'  parent={parent_id}")

        if dry_run:
            continue

        try:
            html = md_to_html(path.read_text(encoding="utf-8", errors="replace"))
            page_id = create_page(client, title, html, parent_id)
            state[rel_str] = {"kind": "page", "id": page_id, "title": title}
            save_state(state)
            print(f"      -> created {page_id}")
        except RuntimeError as e:
            err_msg = str(e)
            print(f"      ! create failed: {err_msg[:200]}")
            # Common: title already exists. Append filename and retry once.
            if "title" in err_msg.lower() or "409" in err_msg:
                retry_title = f"{title} [{path.stem}]"[:240]
                try:
                    page_id = create_page(client, retry_title, html, parent_id)
                    state[rel_str] = {"kind": "page", "id": page_id, "title": retry_title}
                    save_state(state)
                    print(f"      -> retry succeeded: {page_id}")
                except RuntimeError as e2:
                    print(f"      !! retry failed: {e2}")
                    continue

        migrated_this_run += 1

    print(f"\n== Done. Migrated this run: {migrated_this_run}. State entries: {len(state)} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
