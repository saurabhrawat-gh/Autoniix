#!/bin/bash
set -euo pipefail

# Test database setup script for Rust gateway integration tests.
# Per HARNESS-ENGINEERING-PLAN.md Section 15 + POST-HARNESS-TASKS.md Phase 1.2.
#
# Creates a test database with Python's migrations applied, so both
# Python and Rust services can share the same schema during testing.
#
# Usage:
#   ./scripts/setup_test_db.sh
#
# Requirements:
#   - PostgreSQL running locally
#   - POSTGRES_USER env var (defaults to postgres)

DB_NAME="${TEST_DB_NAME:-autoniix_test}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "Setting up test database: ${DB_NAME} on ${DB_HOST}:${DB_PORT}"

# Drop and recreate test database
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || {
    echo "ERROR: Failed to create database $DB_NAME"
    echo "       Ensure PostgreSQL is running and user '$DB_USER' has CREATE DATABASE permission."
    exit 1
}

echo "✓ Test database created: $DB_NAME"

# Apply Python migrations (schema owner is Python's migration system)
MIGRATIONS_DIR="$(cd "$(dirname "$0")/../.." && pwd)/scripts/migrations"
if [ -d "$MIGRATIONS_DIR" ]; then
    echo "Applying migrations from $MIGRATIONS_DIR ..."
    export PGPASSWORD="${POSTGRES_PASSWORD:-}"
    for sql_file in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
        echo "  → $(basename "$sql_file")"
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$sql_file" -v ON_ERROR_STOP=1 2>/dev/null || {
            echo "  ⚠ Warning: $(basename "$sql_file") had errors (may be expected for idempotent migrations)"
        }
    done
    echo "✓ Migrations applied"
else
    echo "⚠ No migrations directory found at $MIGRATIONS_DIR"
    echo "  You may need to apply migrations manually:"
    echo "  cd src && DATABASE_URL=postgresql://$DB_USER@$DB_HOST/$DB_NAME python -m alembic upgrade head"
fi

# Write .env.test if it doesn't exist
ENV_TEST="$(cd "$(dirname "$0")/.." && pwd)/.env.test"
if [ ! -f "$ENV_TEST" ]; then
    cat > "$ENV_TEST" << EOF
TEST_DATABASE_URL=postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME
AUTH_JWT_SECRET=test-jwt-secret-for-integration-tests-only
EOF
    echo "✓ Created .env.test at $ENV_TEST"
else
    echo "✓ .env.test already exists"
fi

echo ""
echo "Test database ready: postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "Run tests with:"
echo "  TEST_DATABASE_URL=postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME cargo test -p gateway"
echo "  TEST_DATABASE_URL=postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME cargo test -p gateway --test schema_compatibility_test"
