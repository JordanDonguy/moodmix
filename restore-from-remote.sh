#!/bin/bash
set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:-dropbox:moodmix-backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"

command -v rclone >/dev/null || { echo "rclone not installed: brew install rclone"; exit 1; }

mkdir -p tmp

LATEST=$(rclone lsf "${RCLONE_REMOTE}" --include "*.dump" | sort -r | head -n1)
if [ -z "${LATEST}" ]; then
    echo "No backups found in ${RCLONE_REMOTE}"
    exit 1
fi

echo "Latest backup: ${LATEST}"
rclone copy "${RCLONE_REMOTE}/${LATEST}" tmp/

echo "Recreating local moodmix database..."
docker compose -f "${COMPOSE_FILE}" exec -T db \
    psql -U moodmix -d postgres -c "DROP DATABASE IF EXISTS moodmix WITH (FORCE);"
docker compose -f "${COMPOSE_FILE}" exec -T db \
    psql -U moodmix -d postgres -c "CREATE DATABASE moodmix OWNER moodmix;"

echo "Restoring dump..."
docker compose -f "${COMPOSE_FILE}" exec -T db \
    pg_restore -U moodmix -d moodmix --no-owner --no-acl < "tmp/${LATEST}"

rm -f "tmp/${LATEST}"
echo "Restore complete from ${LATEST}"
