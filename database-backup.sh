#!/bin/bash
set -e

#Set up the backup logger 
BACKUP_LOG="/app/logs/backup.log"
exec 1> >(tee -a "$BACKUP_LOG")
exec 2> >(tee -a "$BACKUP_LOG" >&2)

echo "=== Backup started at $(date) ==="
echo ""

#Generate timestamp and file names
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backup_${DATE}.sql"
COMPRESSED_FILE="backup_${DATE}.sql.gz"


echo "Starting PostgreSQL backup at $(date)"
#Set password for pg_dump
export PGPASSWORD=$POSTGRES_PASSWORD

#Create backup using network connection (no docker exec needed)
echo "Creating database backup..."
pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /backups/$BACKUP_FILE

#Apply permission to created file (User: Owner only, Actions: Read/Write Only)
chmod 600 /backups/$BACKUP_FILE

#Compress backup with gzip
echo "Compressing backup file..."
gzip /backups/$BACKUP_FILE

echo "Backup created: /backups/$COMPRESSED_FILE"
chmod 600 /backups/$COMPRESSED_FILE
echo ""

#Upload backup to S3 bucket and remove local compressed file after successful upload
echo "Uploading to S3..."
echo ""
if aws s3 cp /backups/$COMPRESSED_FILE s3://$S3_BUCKET/postgres-backups/$COMPRESSED_FILE; then
    echo "Backup uploaded to S3 successfully"
    #remove local backup after S3 upload
    rm /backups/$COMPRESSED_FILE
    echo "Local backup file removed"
else
    echo "ERROR: S3 upload failed, keeping local backup"
    exit 1
fi

#Clean up old local backups (keep last backup file only)
echo "Cleaning up old local backups..."
ls -t /backups/backup_*.sql.gz 2>/dev/null | tail -n +2 | xargs -r rm -f


#S3 Cleanup (keeping last 7 backups only)
echo "Cleaning up old S3 backups (keeping last 7)..."
aws s3 ls s3://$S3_BUCKET/postgres-backups/ \
    | sort \
    | head -n -7 \
    | awk '{print $4}' \
    | while read file; do
        if [ ! -z "$file" ] && [[ $file == backup_* ]]; then
            aws s3 rm s3://$S3_BUCKET/postgres-backups/$file
            echo "Deleted old S3 backup: $file"
        fi
    done

echo ""
echo "Backup process completed successfully at $(date)"
echo "=================================================="
echo ""
echo ""