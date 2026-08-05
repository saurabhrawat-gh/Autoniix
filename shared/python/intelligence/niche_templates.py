"""Niche template loader.

Templates live in ``niche_templates.json`` (sibling file) so non-engineers
can edit / add presets without touching Python. The loader caches the
parsed file on first read.

Each template carries:

* ``id``            \u2014 stable slug used as the API key
* ``label``         \u2014 human-readable name shown in the wizard
* ``niche`` / ``sub_niche`` \u2014 channel-table fields
* ``summary``       \u2014 one-line pitch shown in the picker
* ``starter_topics``\u2014 4 example topics to seed ``topics_queue``
* ``dna``           \u2014 the same Brand DNA dict that
  ``/api/channels/generate-brand-dna`` returns, so the wizard can drop a
  template straight into the existing form without any reshaping.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_TEMPLATE_FILE = Path(__file__).parent / "niche_templates.json"


@lru_cache(maxsize=1)
def _load_all() -> list[dict[str, Any]]:
    raw = json.loads(_TEMPLATE_FILE.read_text())
    templates = raw.get("templates", [])
    if not isinstance(templates, list):
        raise ValueError("niche_templates.json: 'templates' must be a list")
    seen_ids: set[str] = set()
    for t in templates:
        tid = t.get("id")
        if not tid or not isinstance(tid, str):
            raise ValueError(f"niche_templates.json: template missing 'id': {t!r}")
        if tid in seen_ids:
            raise ValueError(f"niche_templates.json: duplicate template id {tid!r}")
        seen_ids.add(tid)
        for required in ("label", "niche", "dna"):
            if required not in t:
                raise ValueError(f"niche_templates.json: template {tid!r} missing {required!r}")
        if not isinstance(t["dna"], dict):
            raise ValueError(f"niche_templates.json: template {tid!r} 'dna' must be a dict")
    return templates


def list_templates() -> list[dict[str, Any]]:
    """Return all templates in registration order (suitable for an API list).

    The DNA dict is included so the wizard can render a preview without a
    second round-trip.
    """
    return [dict(t) for t in _load_all()]


def get_template(template_id: str) -> dict[str, Any] | None:
    for t in _load_all():
        if t["id"] == template_id:
            return dict(t)
    return None


def reset_cache() -> None:
    """Drop the cached parse \u2014 used by tests after editing the JSON file."""
    _load_all.cache_clear()
