#!/usr/bin/env python3
"""
Extract OpenAPI schemas from Python dashboard and Rust gateway.
Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 1.
"""

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

SCHEMAS_DIR = Path(__file__).parent / "schemas"
SCHEMAS_DIR.mkdir(exist_ok=True)


def extract_python_schema(base_url: str = "http://localhost:8000") -> dict[str, Any]:
    """
    Extract OpenAPI schema from Python FastAPI dashboard.
    FastAPI auto-generates schema at /openapi.json.
    """
    logger.info("extracting_python_schema", base_url=base_url)

    try:
        response = httpx.get(f"{base_url}/openapi.json", timeout=10.0)
        response.raise_for_status()
        schema = response.json()

        logger.info(
            "python_schema_extracted",
            endpoints=len(schema.get("paths", {})),
            version=schema.get("openapi"),
        )
        return schema
    except httpx.HTTPError as e:
        logger.error("python_schema_extraction_failed", error=str(e))
        raise


def extract_rust_schema(base_url: str = "http://localhost:8080") -> dict[str, Any]:
    """
    Extract OpenAPI schema from Rust gateway.

    Option A: If Rust has /openapi.json endpoint (via utoipa)
    Option B: Generate from code annotations (requires utoipa setup)
    Option C: Handwritten schema (fallback)
    """
    logger.info("extracting_rust_schema", base_url=base_url)

    try:
        response = httpx.get(f"{base_url}/openapi.json", timeout=10.0)
        if response.status_code == 200:
            schema = response.json()
            logger.info(
                "rust_schema_extracted_from_endpoint",
                endpoints=len(schema.get("paths", {})),
            )
            return schema
    except httpx.HTTPError:
        pass

    handwritten_path = Path(__file__).parent.parent.parent / "docs" / "openapi" / "rust-gateway.yaml"
    if handwritten_path.exists():
        logger.info("using_handwritten_rust_schema", path=str(handwritten_path))
        import yaml

        with open(handwritten_path) as f:
            return yaml.safe_load(f)

    logger.warning(
        "rust_schema_not_found",
        message="Rust gateway does not expose /openapi.json. "
        "Either add utoipa annotations or create handwritten schema at "
        f"{handwritten_path}",
    )
    return {"openapi": "3.0.0", "info": {"title": "Rust Gateway", "version": "0.1.0"}, "paths": {}}


def save_schema(schema: dict[str, Any], filename: str) -> None:
    """Save schema to JSON file."""
    output_path = SCHEMAS_DIR / filename
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)
    logger.info("schema_saved", path=str(output_path), size=len(json.dumps(schema)))


def main():
    """Extract schemas from both services."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract OpenAPI schemas")
    parser.add_argument("--python-url", default="http://localhost:8000", help="Python dashboard URL")
    parser.add_argument("--rust-url", default="http://localhost:8080", help="Rust gateway URL")
    parser.add_argument("--python-only", action="store_true", help="Extract Python schema only")
    parser.add_argument("--rust-only", action="store_true", help="Extract Rust schema only")
    args = parser.parse_args()

    try:
        if not args.rust_only:
            python_schema = extract_python_schema(args.python_url)
            save_schema(python_schema, "python-dashboard.json")

        if not args.python_only:
            rust_schema = extract_rust_schema(args.rust_url)
            save_schema(rust_schema, "rust-gateway.json")

        logger.info("schema_extraction_complete", schemas_dir=str(SCHEMAS_DIR))
        return 0

    except Exception as e:
        logger.error("schema_extraction_failed", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
