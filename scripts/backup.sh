#!/usr/bin/env bash
# Daily backup of Postgres (app DB) + MinIO `prod/` prefix to a chosen
# remote (Cloudflare R2 by default). Idempotent and safe to cron.
#
# Cron example (daily 03:30 UTC):
#   30 3 * * * /opt/autoniix/scripts/backup.sh >> /var/log/autoniix-backup.log 2>&1
#
# Required env (sourced from .env if present):
#   DB_NAME, DB_USER, DB_PASSWORD     — Postgres
#   S3_ACCESS_KEY, S3_SECRET_KEY,     — local MinIO source
#   S3_BUCKET
#   BACKUP_R2_ENDPOINT                — e.g. https://<accid>.r2.cloudflarestorage.com
#   BACKUP_R2_ACCESS_KEY,
#   BACKUP_R2_SECRET_KEY,
#   BACKUP_R2_BUCKET                  — destination R2 bucket (must exist)
#
# Skips the R2 step gracefully if BACKUP_R2_* are not set — local snapshots
# still land under ./backups/ for manual offsite copy.
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="backups/${STAMP}"
mkdir -p "${OUT_DIR}"
echo "[backup] writing to ${OUT_DIR}"

# ── Postgres dump (compressed custom format) ────────────────
echo "[backup] postgres dump..."
docker compose exec -T postgres-app pg_dump \
    -U "${DB_USER:-app}" \
    -d "${DB_NAME:-autoniix}" \
    -Fc --no-owner --no-privileges \
    > "${OUT_DIR}/postgres-app.dump"
echo "[backup] postgres dump size: $(du -h "${OUT_DIR}/postgres-app.dump" | cut -f1)"

# ── MinIO sync (prod/ + public/ prefixes only — test/ is throwaway) ──
echo "[backup] minio mirror..."
docker run --rm --network autoniix_autoniix-net \
    -v "$(pwd)/${OUT_DIR}/minio:/out" \
    -e MC_HOST_local="http://${S3_ACCESS_KEY:-minioadmin}:${S3_SECRET_KEY:-minioadmin}@minio:9000" \
    minio/mc:latest -- mirror --quiet --overwrite \
        "local/${S3_BUCKET:-autoniix}/prod" /out/prod || true
docker run --rm --network autoniix_autoniix-net \
    -v "$(pwd)/${OUT_DIR}/minio:/out" \
    -e MC_HOST_local="http://${S3_ACCESS_KEY:-minioadmin}:${S3_SECRET_KEY:-minioadmin}@minio:9000" \
    minio/mc:latest -- mirror --quiet --overwrite \
        "local/${S3_BUCKET:-autoniix}/public" /out/public || true

# ── Optional: push to R2 ────────────────────────────────────
if [ -n "${BACKUP_R2_ENDPOINT:-}" ] && [ -n "${BACKUP_R2_ACCESS_KEY:-}" ] \
   && [ -n "${BACKUP_R2_SECRET_KEY:-}" ] && [ -n "${BACKUP_R2_BUCKET:-}" ]; then
    echo "[backup] mirroring to R2..."
    docker run --rm \
        -v "$(pwd)/${OUT_DIR}:/in" \
        -e MC_HOST_r2="https://${BACKUP_R2_ACCESS_KEY}:${BACKUP_R2_SECRET_KEY}@${BACKUP_R2_ENDPOINT#https://}" \
        minio/mc:latest -- cp -r /in "r2/${BACKUP_R2_BUCKET}/${STAMP}"
    echo "[backup] R2 push complete: ${BACKUP_R2_BUCKET}/${STAMP}"
else
    echo "[backup] BACKUP_R2_* not set — skipping offsite push (local copy retained)"
fi

# ── Local retention: keep last 7 daily snapshots ────────────
ls -1dt backups/*/ 2>/dev/null | tail -n +8 | xargs -r rm -rf
echo "[backup] done"
