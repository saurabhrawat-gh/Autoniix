#!/usr/bin/env bash
# Daily backup of Postgres (app DB) + MinIO `prod/` + `public/` prefixes.
#
# Default target: ${BACKUP_LOCAL_DIR:-/mnt/backups}  (created by vps_bootstrap.sh)
# Optional offsite: any S3-compatible target via BACKUP_S3_* env vars.
# Backwards-compat: legacy BACKUP_R2_* are also honored.
#
# Cron example (daily 03:30 UTC) on the VPS:
#   30 3 * * * /home/autoniix/autoniix/scripts/backup.sh >> /var/log/autoniix-backup.log 2>&1
#
# Required env (sourced from .env if present):
#   DB_NAME, DB_USER, DB_PASSWORD     — Postgres
#   S3_ACCESS_KEY, S3_SECRET_KEY,     — local MinIO source
#   S3_BUCKET
#   BACKUP_LOCAL_DIR                  — where daily snapshots land (default /mnt/backups)
#   BACKUP_RETENTION_DAYS             — local retention (default 14)
#
# Optional offsite (any S3-compatible — Hostinger / B2 / R2 / S3):
#   BACKUP_S3_ENDPOINT
#   BACKUP_S3_ACCESS_KEY
#   BACKUP_S3_SECRET_KEY
#   BACKUP_S3_BUCKET
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

LOCAL_DIR="${BACKUP_LOCAL_DIR:-/mnt/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${LOCAL_DIR}/${STAMP}"

# Fallback to repo-local ./backups if /mnt/backups is missing (dev runs).
if [ ! -d "${LOCAL_DIR}" ]; then
    echo "[backup] ${LOCAL_DIR} missing — falling back to ./backups"
    LOCAL_DIR="$(pwd)/backups"
    OUT_DIR="${LOCAL_DIR}/${STAMP}"
fi

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
NET="${COMPOSE_NETWORK:-autoniix_autoniix-net}"
for PREFIX in prod public; do
    docker run --rm --network "${NET}" \
        -v "${OUT_DIR}/minio:/out" \
        -e MC_HOST_local="http://${S3_ACCESS_KEY:-minioadmin}:${S3_SECRET_KEY:-minioadmin}@minio:9000" \
        minio/mc:latest -- mirror --quiet --overwrite \
            "local/${S3_BUCKET:-autoniix}/${PREFIX}" "/out/${PREFIX}" || true
done

# ── Optional: push to offsite S3-compatible target ──────────
push_to_s3() {
    local endpoint="$1" access="$2" secret="$3" bucket="$4"
    [ -n "${endpoint}" ] && [ -n "${access}" ] && [ -n "${secret}" ] && [ -n "${bucket}" ] || return 1
    echo "[backup] mirroring to ${endpoint}/${bucket}/${STAMP}..."
    docker run --rm \
        -v "${OUT_DIR}:/in" \
        -e MC_HOST_offsite="https://${access}:${secret}@${endpoint#https://}" \
        minio/mc:latest -- cp -r /in "offsite/${bucket}/${STAMP}"
    echo "[backup] offsite push complete: ${bucket}/${STAMP}"
}

if push_to_s3 "${BACKUP_S3_ENDPOINT:-}" "${BACKUP_S3_ACCESS_KEY:-}" "${BACKUP_S3_SECRET_KEY:-}" "${BACKUP_S3_BUCKET:-}"; then
    :
elif push_to_s3 "${BACKUP_R2_ENDPOINT:-}" "${BACKUP_R2_ACCESS_KEY:-}" "${BACKUP_R2_SECRET_KEY:-}" "${BACKUP_R2_BUCKET:-}"; then
    :
else
    echo "[backup] no offsite target configured — local copy retained at ${OUT_DIR}"
fi

# ── Local retention ──────────────────────────────────
echo "[backup] pruning local snapshots older than ${RETENTION_DAYS} days"
find "${LOCAL_DIR}" -maxdepth 1 -mindepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} +
echo "[backup] done"
