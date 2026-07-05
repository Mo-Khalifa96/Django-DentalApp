#!/bin/bash

set -e

echo "Pulling latest code before..."

#Reset to be overlayed files to their default state
git checkout -- backup.Dockerfile database-backup.sh database-backup-cron.sh docker-compose.dev.yml docker-compose.prod.yml 2>/dev/null || true

#pull new code
git pull origin main || \
{ git reset --hard && git clean -fd && git pull origin main; } || \
{ git pull --rebase origin main && git pull origin main; }

#load env variables
set -a
source .env
set +a

#Apply provider-specific overlay
if [ "${CLOUD_PROVIDER:-aws}" = "oracle" ]; then
    echo "Applying Oracle overlay files from deploy/oracle/..."
    cp deploy/oracle/backup.Dockerfile ./backup.Dockerfile || { echo "Failed to overlay backup.Dockerfile"; exit 1; }
    cp deploy/oracle/database-backup.sh ./database-backup.sh || { echo "Failed to overlay database-backup.sh"; exit 1; }
    cp deploy/oracle/database-backup-cron.sh ./database-backup-cron.sh || { echo "Failed to overlay database-backup-cron.sh"; exit 1; }
    cp deploy/oracle/docker-compose.dev.yml ./docker-compose.dev.yml || { echo "Failed to overlay docker-compose.dev.yml"; exit 1; }
    cp deploy/oracle/docker-compose.prod.yml ./docker-compose.prod.yml || { echo "Failed to overlay docker-compose.prod.yml"; exit 1; }
fi

echo "App updated successfully."
