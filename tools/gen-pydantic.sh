#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OPENAPI_FILE="$PROJECT_ROOT/libs/ts/contracts/openapi.json"
OUTPUT_DIR="$PROJECT_ROOT/libs/python/contracts"

if [ ! -f "$OPENAPI_FILE" ]; then
  echo "❌ OpenAPI spec not found: $OPENAPI_FILE"
  echo "Run 'npm run gen-openapi' in libs/ts/contracts first"
  exit 1
fi

echo "🔄 Generating Pydantic models from OpenAPI spec..."

uv run datamodel-codegen \
  --input "$OPENAPI_FILE" \
  --input-file-type openapi \
  --output "$OUTPUT_DIR/models.py" \
  --output-model-type pydantic_v2.BaseModel \
  --use-standard-collections \
  --use-schema-description \
  --use-title-as-name \
  --field-constraints \
  --snake-case-field \
  --use-double-quotes \
  --target-python-version 3.12

echo "✅ Pydantic models generated: $OUTPUT_DIR/models.py"
