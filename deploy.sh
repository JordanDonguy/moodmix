#!/bin/bash
set -e

cd /srv/moodmix

git pull

# Backup current image as fallback
sudo docker tag moodmix-api:latest moodmix-api:backup 2>/dev/null || true

# Build new image
sudo docker compose -f docker-compose.prod.yml build

# Run migrations in a temporary container first
if sudo docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head; then
    # If migrations succeed, bring up new version
    sudo docker compose -f docker-compose.prod.yml up -d
    # Remove dangling images
    sudo docker image prune -f
    echo "Deploy complete"
else
    # Rollback if migration fails
    echo "Migrations failed! Rolling back..."
    sudo docker tag moodmix-api:backup moodmix-api:latest
    sudo docker compose -f docker-compose.prod.yml up -d
    exit 1
fi
