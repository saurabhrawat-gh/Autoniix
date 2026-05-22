#!/usr/bin/env python3
"""Phase 2: Create custom fields for project AE.

Fields created:
  - Environment  (select): local | dev | staging | prod
  - Severity     (select): P0-Critical | P1-High | P2-Medium | P3-Low
  - Layer        (select): UI | Gateway | Service | DB | Auth | Worker | Infra | Test

Idempotent: safe to re-run — skips fields that already exist.
"""
from __future__ import annotations

import sys
from _atlassian import AtlassianClient, load_config

JIRA_PROJECT_KEY = "AE"
PROJECT_ID = "10001"

CUSTOM_FIELDS = [
    {
        "name": "Environment",
        "description": "Deployment environment where the issue was found or is relevant.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searcherKey": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "options": ["local", "dev", "staging", "prod"],
    },
    {
        "name": "Severity",
        "description": "How severe is the impact of this issue.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searcherKey": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "options": ["P0-Critical", "P1-High", "P2-Medium", "P3-Low"],
    },
    {
        "name": "Layer",
        "description": "Which architectural layer is affected.",
        "type": "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searcherKey": "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "options": ["UI", "Gateway", "Service", "DB", "Auth", "Worker", "Infra", "Test"],
    },
]


def get_existing_custom_fields(client: AtlassianClient) -> dict[str, dict]:
    """Return {name: field} for all existing custom fields."""
    fields = client.jira_get("/field")
    return {f["name"]: f for f in fields if f.get("custom", False)}


def get_or_create_field(
    client: AtlassianClient,
    existing: dict[str, dict],
    spec: dict,
) -> str:
    """Return field ID, creating the field if it doesn't exist."""
    if spec["name"] in existing:
        fid = existing[spec["name"]]["id"]
        print(f"  - '{spec['name']}' already exists (id={fid})")
        return fid

    payload = {
        "name": spec["name"],
        "description": spec["description"],
        "type": spec["type"],
        "searcherKey": spec["searcherKey"],
    }
    try:
        new_field = client.jira_post("/field", payload)
        fid = new_field.get("id")
        print(f"  + created '{spec['name']}' (id={fid})")
        return fid
    except RuntimeError as e:
        print(f"  ! failed to create '{spec['name']}': {e}")
        return ""


def get_default_context_id(client: AtlassianClient, field_id: str) -> str | None:
    """Return the default context ID for a custom field."""
    try:
        resp = client.jira_get(f"/field/{field_id}/context")
        values = resp.get("values", [])
        if values:
            return str(values[0]["id"])
    except Exception as e:
        print(f"    ! could not fetch context for {field_id}: {e}")
    return None


def add_options(
    client: AtlassianClient,
    field_id: str,
    context_id: str,
    options: list[str],
) -> None:
    """Add select options to a field context (skips duplicates automatically)."""
    try:
        existing_resp = client.jira_get(
            f"/field/{field_id}/context/{context_id}/option"
        )
        existing_names = {o["value"] for o in existing_resp.get("values", [])}
    except Exception:
        existing_names = set()

    to_add = [v for v in options if v not in existing_names]
    if not to_add:
        print(f"    all options already exist")
        return

    payload = {"options": [{"value": v, "disabled": False} for v in to_add]}
    try:
        client.jira_post(
            f"/field/{field_id}/context/{context_id}/option", payload
        )
        print(f"    added options: {to_add}")
    except RuntimeError as e:
        print(f"    ! failed to add options: {e}")


def main() -> int:
    cfg = load_config()
    client = AtlassianClient(cfg)

    print(f"== Phase 2: Create custom fields for project {JIRA_PROJECT_KEY} ==\n")

    existing = get_existing_custom_fields(client)

    for spec in CUSTOM_FIELDS:
        print(f"\n[{spec['name']}]")
        field_id = get_or_create_field(client, existing, spec)
        if not field_id:
            continue

        context_id = get_default_context_id(client, field_id)
        if context_id:
            print(f"    context id={context_id}")
            add_options(client, field_id, context_id, spec["options"])
        else:
            print(f"    ! no context found — options not set")

    print("\n== Phase 2 complete ==")
    print(
        "\nNOTE: To see these fields on issue create/edit screens, go to:\n"
        f"  {cfg.base_url}/jira/software/projects/{JIRA_PROJECT_KEY}/settings/issuetypes\n"
        "  Click each issue type → Fields tab → Add field → pick Environment/Severity/Layer"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
