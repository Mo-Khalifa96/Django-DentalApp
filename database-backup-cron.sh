#!/bin/bash

set -e

#Create cron job for database backup 
echo "Creating database backup cron job..."
echo ""

#Fetch and save relevant environment variables in env.sh for cron to access
printenv | grep -E 'POSTGRES_|AWS_|S3_BUCKET' | sed 's/^/export /' > /app/env.sh

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

#Start cron daemon in foreground
cron -f