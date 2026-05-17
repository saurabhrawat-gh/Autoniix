#!/usr/bin/env bash
# Restore Postgres (app DB) and MinIO from a backup snapshot produced by
# scripts/backup.sh.
#
# Usage:
#   bash scripts/restore.sh                     # restore from latest snapshot
#   bash scripts/restore.sh 20260510T033000Z    # restore a specific stamp
#
# ⚠  DESTRUCTIVE: this will DROP and recreate the yt_automation database and
#    overwrite MinIO prod/ + public/ prefixes. Run only when you are certain.
#
# Required env (sourced from .env if present):
#   DB_NAME, DB_USER, DB_PASSWORD     — Postgres target
#   S3_ACCESS_KEY, S3_SECRET_KEY,     — local MinIO
#   S3_BUCKET
#
# If the snapshot is on Cloudflare R2 rather than local disk, first copy it:
#   mc cp --recursive r2/<bucket>/<stamp>/ backups/<stamp>/
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

# Select snapshot
if [ -n "${1:-}" ]; then
    STAMP="$1"
else
    # Pick the most recent local snapshot
    STAMP=$(ls -1dt backups/*/ 2>/dev/null | head -1 | xargs basename)
    if [ -z "${STAMP:-}" ]; then
        echo "❌ No local snapshots found under ./backups/. Pass a timestamp or copy from R2."
        exit 1
    fi
fi

IN_DIR="backups/${STAMP}"

if [ ! -d "${IN_DIR}" ]; then
    echo "❌ Snapshot directory not found: ${IN_DIR}"
    echo "   Available snapshots:"
    ls -1 backups/ 2>/dev/null | head -20 || echo "   (none)"
    exit 1
fi

echo ""
echo "  ⚠  RESTORE from snapshot: ${STAMP}"
echo "     Postgres DB  : ${DB_NAME:-yt_automation} will be dropped + recreated"
echo "     MinIO        : prod/ + public/ prefixes will be overwritten"
echo ""
read -p "  Type 'restore' to confirm: " confirm
if [ "${confirm}" != "restore" ]; then
    echo "❌ Aborted"
    exit 1
fi

echo ""
echo "[restore] reading from ${IN_DIR}"

# Postgres restore
DUMP="${IN_DIR}/postgres-app.dump"
if [ ! -f "${DUMP}" ]; then
    echo "❌ Postgres dump not found: ${DUMP}"
    exit 1
fi

echo "[restore] dropping and recreating database ${DB_NAME:-yt_automation}..."
docker compose exec -T postgres-app psql \
    -U "${DB_USER:-app}" -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME:-yt_automation}' AND pid <> pg_backend_pid();" \
    > /dev/null 2>&1 || true
docker compose exec -T postgres-app psql \
    -U "${DB_USER:-app}" -d postgres \
    -c "DROP DATABASE IF EXISTS \"${DB_NAME:-yt_automation}\";" \
    > /dev/null
docker compose exec -T postgres-app psql \
    -U "${DB_USER:-app}" -d postgres \
    -c "CREATE DATABASE \"${DB_NAME:-yt_automation}\" OWNER \"${DB_USER:-app}\";" \
    > /dev/null

echo "[restore] restoring postgres dump (this may take a few minutes)..."
docker compose exec -T postgres-app pg_restore \
    -U "${DB_USER:-app}" \
    -d "${DB_NAME:-yt_automation}" \
    --no-owner --no-privileges \
    --if-exists --clean \
    --exit-on-error \
    < "${DUMP}"
echo "[restore] postgres: done"

# MinIO restore
MINIO_DIR="${IN_DIR}/minio"

if [ -d "${MINIO_DIR}/prod" ] || [ -d "${MINIO_DIR}/public" ]; then
    echo "[restore] mirroring minio data..."
    for prefix in prod public; do
        if [ -d "${MINIO_DIR}/${prefix}" ]; then
            docker run --rm --network autoniix_autoniix-net \
                -v "$(pwd)/${MINIO_DIR}:/in" \
                -e MC_HOST_local="http://${S3_ACCESS_KEY:-minioadmin}:${S3_SECRET_KEY:-minioadmin}@minio:9000" \
                minio/mc:latest -- mirror --quiet --overwrite \
                    "/in/${prefix}" "local/${S3_BUCKET:-autoniix}/${prefix}"
            echo "[restore] minio/${prefix}: done"
        fi
    done
else
    echo "[restore] no minio data found in snapshot, skipping"
fi

echo ""
echo "✅ Restore complete from snapshot: ${STAMP}"
echo "   Restart services to pick up the restored data:"
echo "     make restart-app"
