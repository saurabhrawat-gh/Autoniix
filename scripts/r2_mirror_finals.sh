#!/usr/bin/env bash
# Mirror approved/delivered videos from MinIO `prod/renders/` to Cloudflare
# R2 so YouTube delivery (and any external sharing) can fetch from a public
# CDN-backed origin instead of hitting the in-cluster MinIO box.
#
# Cron example (every 30 minutes):
#   */30 * * * * /opt/autoniix/scripts/r2_mirror_finals.sh >> /var/log/autoniix-r2.log 2>&1
#
# Required env:
#   S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET
#   R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET
#
# Idempotent — `mc mirror` only copies new/changed objects.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

if [ -z "${R2_ENDPOINT:-}" ] || [ -z "${R2_ACCESS_KEY:-}" ] \
   || [ -z "${R2_SECRET_KEY:-}" ] || [ -z "${R2_BUCKET:-}" ]; then
    echo "[r2-mirror] R2_* env not set — skipping (configure to enable)"
    exit 0
fi

docker run --rm --network autoniix_autoniix-net \
    -e MC_HOST_local="http://${S3_ACCESS_KEY:-minioadmin}:${S3_SECRET_KEY:-minioadmin}@minio:9000" \
    -e MC_HOST_r2="https://${R2_ACCESS_KEY}:${R2_SECRET_KEY}@${R2_ENDPOINT#https://}" \
    minio/mc:latest -- mirror --quiet --overwrite \
        "local/${S3_BUCKET:-autoniix}/prod/renders" \
        "r2/${R2_BUCKET}/renders"

echo "[r2-mirror] done at $(date -u +%FT%TZ)"
