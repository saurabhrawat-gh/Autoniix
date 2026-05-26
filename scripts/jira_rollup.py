#!/usr/bin/env python3
"""Jira hierarchy status rollup: sub-task → Story → Epic.

Stories and Epics get ONLY 3 statuses: To Do | In Progress | Done

Rules:
  all children Prod Verified/Done         → Done
  all children To Do                      → To Do
  otherwise                               → In Progress

Usage:
  JIRA_BASE_URL=... JIRA_EMAIL=... JIRA_API_TOKEN=... python3 scripts/jira_rollup.py AE-123
"""
from __future__ import annotations
import base64, json, os, sys, urllib.error, urllib.parse, urllib.request

DONE_STATUSES = frozenset({"Prod Verified", "Done"})
TODO, IN_PROGRESS, DONE = "To Do", "In Progress", "Done"

_BASE = (os.environ.get("JIRA_BASE_URL") or "").rstrip("/")
_AUTH = base64.b64encode(
    f"{os.environ.get('JIRA_EMAIL','')}:{os.environ.get('JIRA_API_TOKEN','')}".encode()
).decode()


def _call(method, path, body=None):
    url = f"{_BASE}/rest/api/3/{path.lstrip('/')}"
    data = json.dumps(body).encode() if body else None
    hdrs = {"Authorization": f"Basic {_AUTH}", "Accept": "application/json"}
    if data:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} {method} {path}: {e.read().decode()[:200]}")
        return None


def get_issue(key):
    return _call("GET", f"issue/{key}?fields=status,issuetype,parent,summary")


def get_children(parent_key):
    enc = urllib.parse.quote(f"parent = {parent_key} ORDER BY key ASC")
    r = _call("GET", f"search?jql={enc}&fields=status,summary&maxResults=200")
    return (r or {}).get("issues", [])


def classify(children):
    if not children:
        return None
    ss = [c["fields"]["status"]["name"] for c in children]
    if all(s in DONE_STATUSES for s in ss):
        return DONE
    if all(s == TODO for s in ss):
        return TODO
    return IN_PROGRESS


def transition_to(key, target):
    data = _call("GET", f"issue/{key}/transitions")
    if not data:
        return False
    tid = next((t["id"] for t in data.get("transitions", []) if t["to"]["name"] == target), None)
    if not tid:
        issue = get_issue(key)
        current = issue["fields"]["status"]["name"] if issue else "?"
        if current == target:
            print(f"  ℹ  {key}: already {target!r}")
        else:
            print(f"  ⚠  {key}: no transition to {target!r} from {current!r}")
        return False
    _call("POST", f"issue/{key}/transitions", {"transition": {"id": tid}})
    print(f"  ✅ {key} → {target!r}")
    return True


def rollup(changed_key):
    issue = get_issue(changed_key)
    if not issue:
        print(f"✗ Could not fetch {changed_key}")
        return

    parent_ref = issue["fields"].get("parent")
    if not parent_ref:
        print(f"{changed_key} ({issue['fields']['issuetype']['name']}) has no parent — nothing to roll up")
        return

    # ── Story rollup ──────────────────────────────────────────────────────
    story_key = parent_ref["key"]
    story = get_issue(story_key)
    if not story:
        return
    children = get_children(story_key)
    target = classify(children)
    current = story["fields"]["status"]["name"]
    print(f"\n[Story] {story_key}  children: {[c['fields']['status']['name'] for c in children]}")
    print(f"  current={current!r}  target={target!r}")
    if target and current != target:
        transition_to(story_key, target)
    elif not target:
        print(f"  No children — skip")

    # ── Epic rollup ───────────────────────────────────────────────────────
    epic_ref = story["fields"].get("parent")
    if not epic_ref:
        print(f"\n{story_key} has no parent Epic — done")
        return
    epic_key = epic_ref["key"]
    epic = get_issue(epic_key)
    if not epic:
        return
    stories = get_children(epic_key)
    target = classify(stories)
    current = epic["fields"]["status"]["name"]
    print(f"\n[Epic]  {epic_key}  stories: {[s['fields']['status']['name'] for s in stories]}")
    print(f"  current={current!r}  target={target!r}")
    if target and current != target:
        transition_to(epic_key, target)


if __name__ == "__main__":
    if not _BASE:
        print("ERROR: JIRA_BASE_URL not set"); sys.exit(1)
    if len(sys.argv) < 2:
        print("Usage: jira_rollup.py AE-XXX"); sys.exit(1)
    print(f"Rollup triggered by: {sys.argv[1].upper()}")
    rollup(sys.argv[1].upper())
