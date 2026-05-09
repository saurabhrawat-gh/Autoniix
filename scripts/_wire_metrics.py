"""One-shot script to wire ``instrument_app(...)`` into every FastAPI service.

Idempotent — re-running is a no-op. Inserts a single ``from
src.observability.metrics import instrument_app`` import below the existing
import block and an ``instrument_app(app, service_name="...")`` call right
after the ``app = FastAPI(...)`` line.

Safe against multi-line ``from foo import (\n    a,\n    b,\n)`` imports —
we tokenize and find the last top-level ``Import``/``ImportFrom`` AST node
to anchor the insertion.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = {
    "admin": "src/services/admin/main.py",
    "analytics": "src/services/analytics/main.py",
    "assembly": "src/services/assembly/main.py",
    "assets": "src/services/assets/main.py",
    "brand": "src/services/brand/main.py",
    "dashboard": "src/services/dashboard/main.py",
    "delivery": "src/services/delivery/main.py",
    "direction": "src/services/direction/main.py",
    "editor": "src/services/editor/main.py",
    "research": "src/services/research/main.py",
    "script": "src/services/script/main.py",
    "sheets_sync": "src/services/sheets_sync/main.py",
    "thumbnail": "src/services/thumbnail/main.py",
    "voice": "src/services/voice/main.py",
}
IMPORT_LINE = "from src.observability.metrics import instrument_app"
APP_RE = re.compile(r"^(app\s*=\s*FastAPI\([^\n]*\)\s*)$", re.M)


def wire(service: str, rel_path: str) -> str:
    p = ROOT / rel_path
    src = p.read_text()
    if "instrument_app(" in src and IMPORT_LINE in src:
        return f"skip {service}"

    tree = ast.parse(src)
    last_import = None
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_import = node

    # Insert import after the last top-level import (end_lineno is 1-indexed
    # and inclusive — split src by lines and splice).
    if IMPORT_LINE not in src:
        if last_import is None:
            src = IMPORT_LINE + "\n" + src
        else:
            lines = src.splitlines(keepends=True)
            insert_at = last_import.end_lineno  # type: ignore[attr-defined]
            lines.insert(insert_at, IMPORT_LINE + "\n")
            src = "".join(lines)

    # Insert instrument_app(...) after the FastAPI() line.
    service_label = service.replace("_", "-")
    if "instrument_app(" not in src:
        m = APP_RE.search(src)
        if not m:
            return f"WARN {service}: no `app = FastAPI(...)` line"
        replacement = m.group(1) + f'\ninstrument_app(app, service_name="{service_label}")'
        src = src[: m.start()] + replacement + src[m.end():]

    p.write_text(src)
    # Validate parse before returning.
    ast.parse(src)
    return f"wired {service}"


def main() -> None:
    for svc, rel in SERVICES.items():
        print(wire(svc, rel))


if __name__ == "__main__":
    main()
