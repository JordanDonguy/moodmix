#!/bin/bash
set -euo pipefail

cd /srv/moodmix

TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP_NAME="moodmix-${TIMESTAMP}.dump"
LOCAL_TMP="/tmp/${BACKUP_NAME}"
RCLONE_REMOTE="${RCLONE_REMOTE:-dropbox:moodmix-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

log "Starting backup ${BACKUP_NAME}"

sudo docker compose -f docker-compose.prod.yml exec -T db \
    pg_dump -U moodmix -d moodmix --format=custom --compress=9 \
    > "${LOCAL_TMP}"

SIZE=$(du -h "${LOCAL_TMP}" | cut -f1)
log "Dump complete (${SIZE}), uploading to ${RCLONE_REMOTE}"

rclone copyto "${LOCAL_TMP}" "${RCLONE_REMOTE}/${BACKUP_NAME}"

rm -f "${LOCAL_TMP}"

log "Pruning backups older than ${RETENTION_DAYS} days"
rclone delete --min-age "${RETENTION_DAYS}d" "${RCLONE_REMOTE}" || true

log "Backup complete: ${BACKUP_NAME}"
