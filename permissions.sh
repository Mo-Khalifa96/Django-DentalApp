#!/bin/sh

set -e

#Grant executable permissions to the other scripts
echo "Setting permissions..."
chmod +x /app/update.sh 2>/dev/null || true
chmod +x /app/wait-for-it.sh 2>/dev/null || true
chmod +x /app/database-backup.sh 2>/dev/null || true
chmod +x /app/database-backup-cron.sh 2>/dev/null || true
chmod +x /app/docker-entrypoint.dev.sh 2>/dev/null || true
chmod +x /app/docker-entrypoint.local.sh 2>/dev/null || true
chmod +x /app/docker-entrypoint.prod.sh 2>/dev/null || true
chmod +x /app/renew-certs.sh 2>/dev/null || true
chmod +x /app/sync-files.sh 2>/dev/null || true
chmod +x /app/watch-sync.sh 2>/dev/null || true
chmod 755 /app/logs 2>/dev/null || true

#Set permissions for /backups by postgres-backup service only
if [ "$SERVICE" = "postgres-backup" ]; then
    chmod 700 /backups
else
    echo "Skipping backup permissions for service: ${SERVICE:-unknown}"
fi

#Execute the command passed to the script (the CMD from Dockerfile or command from docker-compose)
echo "Executing command: $@"
exec "$@"