#!/bin/bash
set -e

cd /srv/moodmix

git pull

sudo docker compose -f docker-compose.prod.yml build
sudo docker compose -f docker-compose.prod.yml up -d

echo "Deploy complete"
