"""
REST Contract Validator — validates API responses against OpenAPI schemas.
Per HARNESS-ENGINEERING-PLAN.md Week 1 Day 2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import structlog
from jsonschema import Draft7Validator

logger = structlog.get_logger()


class RESTValidator:
    """Validates REST API responses against OpenAPI 3.0 schemas."""

    def __init__(self, schema_path: str | Path):
        """
        Initialize validator with OpenAPI schema.

        Args:
            schema_path: Path to OpenAPI JSON schema file
        """
        self.schema_path = Path(schema_path)
        with open(self.schema_path) as f:
            self.schema = json.load(f)

        self.paths = self.schema.get("paths", {})
        self.components = self.schema.get("components", {})

        logger.info(
            "rest_validator_initialized",
            schema=self.schema_path.name,
            endpoints=len(self.paths),
        )

    def get_endpoint_schema(
        self,
        method: str,
        path: str,
        response_code: int = 200,
    ) -> dict[str, Any] | None:
        """
        Get response schema for a specific endpoint.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /api/v2/auth/signup)
            response_code: HTTP status code (default: 200)

        Returns:
            JSON schema for the response body, or None if not found
        """
        method = method.lower()

        if path not in self.paths:
            logger.warning("endpoint_not_in_schema", path=path, method=method)
            return None

        endpoint = self.paths[path]
        if method not in endpoint:
            logger.warning("method_not_in_schema", path=path, method=method)
            return None

        responses = endpoint[method].get("responses", {})
        response_def = responses.get(str(response_code))

        if not response_def:
            logger.warning(
                "response_code_not_in_schema",
                path=path,
                method=method,
                code=response_code,
            )
            return None

        content = response_def.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"])

        return schema

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        """
        Resolve $ref pointer to actual schema.

        Args:
            ref: JSON pointer (e.g., #/components/schemas/User)

        Returns:
            Resolved schema object
        """
        if not ref.startswith("#/"):
            raise ValueError(f"Unsupported $ref format: {ref}")

        parts = ref[2:].split("/")
        obj = self.schema

        for part in parts:
            obj = obj.get(part, {})

        return obj

    def validate_response(
        self,
        method: str,
        path: str,
        response_body: dict[str, Any],
        response_code: int = 200,
        strict: bool = True,
    ) -> tuple[bool, list[str]]:
        """
        Validate API response against OpenAPI schema.

        Args:
            method: HTTP method
            path: API path
            response_body: Actual response JSON
            response_code: HTTP status code
            strict: If True, fail on schema not found. If False, pass if schema missing.

        Returns:
            (is_valid, errors) tuple
        """
        schema = self.get_endpoint_schema(method, path, response_code)

        if not schema:
            if strict:
                return False, [f"No schema found for {method} {path} {response_code}"]
            else:
                logger.warning("skipping_validation_no_schema", method=method, path=path)
                return True, []

        validator = Draft7Validator(schema)
        errors = []

        for error in validator.iter_errors(response_body):
            error_msg = f"{'.'.join(str(p) for p in error.path)}: {error.message}"
            errors.append(error_msg)

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(
                "response_valid",
                method=method,
                path=path,
                code=response_code,
            )
        else:
            logger.error(
                "response_invalid",
                method=method,
                path=path,
                code=response_code,
                errors=errors,
            )

        return is_valid, errors

    def validate_openapi(
        self,
        base_url: str,
        method: str,
        path: str,
        request_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_code: int = 200,
    ) -> tuple[bool, httpx.Response, list[str]]:
        """
        Make API request and validate response against schema.

        Args:
            base_url: Base URL of the API (e.g., http://localhost:8080)
            method: HTTP method
            path: API path
            request_body: Request JSON body (for POST/PUT)
            headers: Request headers
            expected_code: Expected HTTP status code

        Returns:
            (is_valid, response, errors) tuple
        """
        url = f"{base_url}{path}"
        headers = headers or {}

        logger.info("making_api_request", method=method, url=url)

        try:
            response = httpx.request(
                method,
                url,
                json=request_body,
                headers=headers,
                timeout=10.0,
            )
        except httpx.HTTPError as e:
            logger.error("api_request_failed", error=str(e))
            return False, None, [f"Request failed: {e}"]

        if response.status_code != expected_code:
            error_msg = f"Expected status {expected_code}, got {response.status_code}"
            logger.error(
                "unexpected_status_code",
                expected=expected_code,
                actual=response.status_code,
            )
            return False, response, [error_msg]

        try:
            response_body = response.json()
        except json.JSONDecodeError:
            return False, response, ["Response is not valid JSON"]

        is_valid, errors = self.validate_response(
            method,
            path,
            response_body,
            response.status_code,
        )

        return is_valid, response, errors


def compare_schemas(
    schema_a_path: str | Path,
    schema_b_path: str | Path,
) -> dict[str, Any]:
    """
    Compare two OpenAPI schemas and report differences.

    Args:
        schema_a_path: Path to first schema (e.g., Python)
        schema_b_path: Path to second schema (e.g., Rust)

    Returns:
        Dictionary with comparison results:
        {
            "endpoints_only_in_a": [...],
            "endpoints_only_in_b": [...],
            "schema_mismatches": [...],
        }
    """
    with open(schema_a_path) as f:
        schema_a = json.load(f)
    with open(schema_b_path) as f:
        schema_b = json.load(f)

    paths_a = set(schema_a.get("paths", {}).keys())
    paths_b = set(schema_b.get("paths", {}).keys())

    only_in_a = paths_a - paths_b
    only_in_b = paths_b - paths_a
    common = paths_a & paths_b

    mismatches = []

    for path in common:
        methods_a = set(schema_a["paths"][path].keys())
        methods_b = set(schema_b["paths"][path].keys())

        if methods_a != methods_b:
            mismatches.append(
                {
                    "path": path,
                    "type": "methods_differ",
                    "schema_a_methods": list(methods_a),
                    "schema_b_methods": list(methods_b),
                }
            )

    result = {
        "endpoints_only_in_a": sorted(only_in_a),
        "endpoints_only_in_b": sorted(only_in_b),
        "schema_mismatches": mismatches,
        "total_endpoints_a": len(paths_a),
        "total_endpoints_b": len(paths_b),
        "common_endpoints": len(common),
    }

    logger.info(
        "schema_comparison_complete",
        only_in_a=len(only_in_a),
        only_in_b=len(only_in_b),
        common=len(common),
        mismatches=len(mismatches),
    )

    return result
