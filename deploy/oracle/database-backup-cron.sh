#!/bin/bash

set -e

echo "Creating database backup cron job..."
echo ""

#Fetch and save relevant environment variables (no AWS_ vars anymore)
printenv | grep -E 'POSTGRES_|OCI_' | sed 's/^/export /' > /app/env.sh

#Add path to env.sh
echo "export PATH=$PATH" >> /app/env.sh

#Set strict permission (owner only (root) - read/write only)
chmod 600 /app/env.sh

#Add the cron job schedule (runs daily 3 AM)
echo '0 3 * * * . /app/env.sh; /app/database-backup.sh' > /etc/cron.d/postgres-backup

#Set permissions for the cron file
chmod 0644 /etc/cron.d/postgres-backup

#Apply the cron job and report
crontab /etc/cron.d/postgres-backup
echo "Cron job created. Backup will run daily at 3:00 AM"
echo ""
echo ""

#Start cron in foreground
cron -f