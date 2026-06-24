#!/usr/bin/env python3
"""
Creates all 38 Jira sprints for the IM project and assigns every Epic/Story/Bug
to its correct sprint via the Jira Agile REST API.

Usage:
    JIRA_EMAIL=admin@autoniix.com JIRA_TOKEN=<token> python scripts/create_sprints.py
"""
import os
import time
import requests
from requests.auth import HTTPBasicAuth

BASE_URL = "https://autoniix.atlassian.net"
EMAIL    = os.environ["JIRA_EMAIL"]
TOKEN    = os.environ["JIRA_TOKEN"]
AUTH     = HTTPBasicAuth(EMAIL, TOKEN)
HEADERS  = {"Content-Type": "application/json", "Accept": "application/json"}

SESSION  = requests.Session()
SESSION.auth    = AUTH
SESSION.headers.update(HEADERS)


def req(method: str, path: str, body: dict | None = None):
    url  = f"{BASE_URL}{path}"
    resp = SESSION.request(method, url, json=body)
    if resp.ok:
        return resp.json() if resp.content else {}
    print(f"  ✗ HTTP {resp.status_code} {method} {path}: {resp.text[:200]}")
    return None


# ── 1. Find the IM board ────────────────────────────────────────────────────
print("⏳  Finding IM board…")
boards = req("GET", "/rest/agile/1.0/board?projectKeyOrId=IM&maxResults=50")
if not boards or not boards.get("values"):
    raise SystemExit("❌  No board found for project IM. Make sure the Scrum board exists.")

board = boards["values"][0]
BOARD_ID = board["id"]
print(f"✅  Board: '{board['name']}' (id={BOARD_ID})")


# ── 2. Sprint definitions ────────────────────────────────────────────────────
# Each entry: (sprint_name, [issue_keys])
SPRINTS = [
    # ── Core ──────────────────────────────────────────────────────────────
    ("Core 1: Auth & Platform", [
        "IM-1",
        "IM-39","IM-40","IM-41","IM-42","IM-43","IM-44","IM-45","IM-46",
        "IM-171","IM-172","IM-173",   # bugs: rate-limit, timing-attack, FK orphan
    ]),
    ("Core 2: Rust Gateway", [
        "IM-2",
        "IM-47","IM-48","IM-49","IM-50","IM-51","IM-52","IM-53",
        "IM-174",                     # bug: Infisical put() no-op
    ]),
    ("Core 3: Rust Harness", [
        "IM-3",
        "IM-54","IM-55","IM-56","IM-57","IM-58","IM-59","IM-60","IM-61","IM-62",
    ]),
    ("Core 4: DB Schema", [
        "IM-4",
        "IM-63","IM-64","IM-65","IM-66","IM-67",
    ]),
    ("Core 5: Temporal Engine", [
        "IM-5",
        "IM-68","IM-69","IM-70","IM-71",
    ]),
    ("Core 6: Brain & Agents", [
        "IM-6",
        "IM-72","IM-73","IM-74","IM-75","IM-76",
    ]),
    ("Core 7: Observability", [
        "IM-7",
        "IM-77","IM-78","IM-79","IM-80",
    ]),

    # ── Pipeline ──────────────────────────────────────────────────────────
    ("Pipeline 1: Research", [
        "IM-8",
        "IM-81","IM-82","IM-83","IM-84",
    ]),
    ("Pipeline 2: Direction", [
        "IM-9",
        "IM-85","IM-86","IM-87",
    ]),
    ("Pipeline 3: Script", [
        "IM-10",
        "IM-88","IM-89","IM-90",
    ]),
    ("Pipeline 4: Voice", [
        "IM-11",
        "IM-91","IM-92","IM-93",
    ]),
    ("Pipeline 5: Assets", [
        "IM-12",
        "IM-94","IM-95","IM-96",
    ]),
    ("Pipeline 6: Thumbnail", [
        "IM-13",
        "IM-97","IM-98",
    ]),
    ("Pipeline 7: Assembly", [
        "IM-14",
        "IM-99","IM-100","IM-101",
    ]),
    ("Pipeline 8: Finishing", [
        "IM-15",
        "IM-102","IM-103","IM-104",
    ]),
    ("Pipeline 9: Delivery", [
        "IM-16",
        "IM-105","IM-106","IM-107","IM-108","IM-109",
    ]),

    # ── Dashboard Features ────────────────────────────────────────────────
    ("Feature: Home", [
        "IM-21",
        "IM-110","IM-111","IM-112","IM-113",
    ]),
    ("Feature: Channels", [
        "IM-22",
        "IM-114","IM-115","IM-116","IM-117",
    ]),
    ("Feature: Content", [
        "IM-23",
        "IM-118","IM-119","IM-120","IM-121",
    ]),
    ("Feature: Library", [
        "IM-24",
        "IM-122","IM-123","IM-124",
    ]),
    ("Feature: Schedule", [
        "IM-25",
        "IM-125","IM-126","IM-127",
    ]),
    ("Feature: Queue", [
        "IM-26",
        "IM-128","IM-129",
    ]),
    ("Feature: Progress", [
        "IM-27",
        "IM-130","IM-131","IM-132",
    ]),
    ("Feature: Review", [
        "IM-28",
        "IM-133","IM-134","IM-135",
    ]),
    ("Feature: Fleet", [
        "IM-29",
        "IM-136","IM-137",
    ]),
    ("Feature: Analytics", [
        "IM-30",
        "IM-138","IM-139","IM-140",
    ]),
    ("Feature: Experiments", [
        "IM-31",
        "IM-141","IM-142",
    ]),
    ("Feature: Notifications", [
        "IM-32",
        "IM-143","IM-144","IM-145",
    ]),
    ("Feature: Workspace", [
        "IM-33",
        "IM-146","IM-147",
    ]),
    ("Feature: Teams", [
        "IM-34",
        "IM-148","IM-149",
    ]),
    ("Feature: Users", [
        "IM-35",
        "IM-150","IM-151",
    ]),
    ("Feature: Providers", [
        "IM-36",
        "IM-152","IM-153","IM-154","IM-155",
    ]),
    ("Feature: Settings", [
        "IM-37",
        "IM-156","IM-157",
    ]),
    ("Feature: Debug", [
        "IM-38",
        "IM-158","IM-159",
    ]),

    # ── Infra ─────────────────────────────────────────────────────────────
    ("Infra: Migration", [
        "IM-17",
        "IM-160","IM-161","IM-162",
    ]),
    ("Infra: SDK", [
        "IM-18",
        "IM-163","IM-164",
    ]),
    ("Infra: DevOps", [
        "IM-19",
        "IM-165","IM-166","IM-167",
        "IM-176",                     # bug: ffmpeg missing from CI
    ]),
    ("Infra: Testing", [
        "IM-20",
        "IM-168","IM-169","IM-170",
        "IM-175",                     # bug: E2E tests skipped in CI
    ]),
]


# ── 3. Create sprints + assign issues ───────────────────────────────────────
created = {}

for name, issues in SPRINTS:
    print(f"\n📋  Creating sprint: {name!r} …")
    sprint = req("POST", "/rest/agile/1.0/sprint", {
        "name": name,
        "originBoardId": BOARD_ID,
    })
    if not sprint:
        print(f"  ⚠️  Skipped (creation failed)")
        continue

    sid = sprint["id"]
    created[name] = sid
    print(f"  ✅  Created sprint id={sid}")

    # Move issues in batches of 50
    for i in range(0, len(issues), 50):
        batch = issues[i:i+50]
        result = req("POST", f"/rest/agile/1.0/sprint/{sid}/issue", {"issues": batch})
        if result is not None:
            print(f"  ✅  Moved {len(batch)} issues: {batch[0]} … {batch[-1]}")
        time.sleep(0.15)   # be gentle with rate limits


# ── 4. Summary ───────────────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print(f"✅  Done!  {len(created)}/{len(SPRINTS)} sprints created.")
for name, sid in created.items():
    print(f"  sprint/{sid:>6}  {name}")
