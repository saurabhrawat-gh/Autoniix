#!/usr/bin/env bash
# Backup-restore drill — non-destructive verification of the backup/restore pipeline.
#
# Steps:
#   1. Take a fresh backup (make backup)
#   2. Restore the latest snapshot to a SEPARATE drill database (autoniix_drill)
#   3. Run basic SQL sanity checks on the drill DB
#   4. Drop the drill DB
#   5. Report pass/fail
#
# The production DB is never touched. The drill DB is always dropped at the end.
#
# Usage:
#   bash scripts/drill_backup_restore.sh
#   make drill-backup-restore
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

DRILL_DB="autoniix_drill"
DB_USER="${DB_USER:-app}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5433}"

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  Backup-restore drill — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "══════════════════════════════════════════════════════════"
echo ""

# ── Step 1: Backup ───────────────────────────────────────────
echo "── 1/4  Taking backup …"
make backup
STAMP=$(ls -1dt backups/*/ 2>/dev/null | head -1 | xargs basename)
DUMP="backups/${STAMP}/postgres-app.dump"
echo "  Snapshot: ${STAMP}"
echo "  Dump:     ${DUMP}"
echo ""

if [ ! -f "${DUMP}" ]; then
    echo "❌  Dump file not found: ${DUMP}"
    exit 1
fi

# ── Step 2: Restore to drill DB ─────────────────────────────
echo "── 2/4  Restoring to drill DB (${DRILL_DB}) …"

# Drop + create the drill DB
docker compose exec -T postgres-app psql -U "${DB_USER}" -d postgres \
    -c "DROP DATABASE IF EXISTS ${DRILL_DB};" 2>/dev/null || true
docker compose exec -T postgres-app psql -U "${DB_USER}" -d postgres \
    -c "CREATE DATABASE ${DRILL_DB} OWNER ${DB_USER};"

# Restore the dump into the drill DB
docker compose exec -T postgres-app pg_restore \
    --username "${DB_USER}" \
    --dbname "${DRILL_DB}" \
    --no-owner \
    --no-acl \
    --jobs 4 \
    "/backups/${STAMP}/postgres-app.dump" || true  # pg_restore exits non-zero on warnings
echo "  Restore complete."
echo ""

# ── Step 3: Sanity checks ────────────────────────────────────
echo "── 3/4  Running SQL sanity checks on ${DRILL_DB} …"

CHECKS_PASSED=0
CHECKS_FAILED=0

check() {
    local label="$1"
    local query="$2"
    local expected="$3"

    result=$(docker compose exec -T postgres-app psql -U "${DB_USER}" -d "${DRILL_DB}" \
        --tuples-only --no-align -c "${query}" 2>/dev/null | tr -d '[:space:]')

    if [ "${result}" = "${expected}" ]; then
        echo "  ✅  ${label}"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo "  ❌  ${label} — expected '${expected}', got '${result}'"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
}

check "schema_migrations table exists" \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='schema_migrations';" "1"

check "users table exists" \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='users';" "1"

check "channels table exists" \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='channels';" "1"

check "audit_log_v2 table exists" \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='audit_log_v2';" "1"

check "feature_flags table exists" \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='feature_flags';" "1"

echo ""

# ── Step 4: Drop drill DB ────────────────────────────────────
echo "── 4/4  Dropping drill DB …"
docker compose exec -T postgres-app psql -U "${DB_USER}" -d postgres \
    -c "DROP DATABASE IF EXISTS ${DRILL_DB};"
echo "  Drill DB dropped."
echo ""

# ── Result ───────────────────────────────────────────────────
echo "══════════════════════════════════════════════════════════"
if [ "${CHECKS_FAILED}" -eq 0 ]; then
    echo "  ✅  PASS — ${CHECKS_PASSED} checks passed, 0 failed"
    echo "  Record this result in the runbook (ops/RUNBOOK.md)."
else
    echo "  ❌  FAIL — ${CHECKS_PASSED} passed, ${CHECKS_FAILED} failed"
    echo "  Investigate before go-live."
    exit 1
fi
echo "══════════════════════════════════════════════════════════"
echo ""
