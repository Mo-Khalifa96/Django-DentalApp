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

#Upload backup to Oracle Object Storage and remove local compressed file after successful upload
echo "Uploading to Oracle Object Storage..."
echo ""
if oci os object put \
    --bucket-name "$OCI_BUCKET" \
    --namespace "$OCI_NAMESPACE" \
    --file /backups/$COMPRESSED_FILE \
    --name postgres-backups/$COMPRESSED_FILE \
    --auth instance_principal; then
    echo "Backup uploaded to Oracle Object Storage successfully"
    
    #remove local backup after S3 upload
    rm /backups/$COMPRESSED_FILE
    echo "Local backup file removed"
else
    echo "ERROR: Object Storage upload failed, keeping local backup"
    exit 1
fi

#Clean up old local backups (keep last backup file only)
echo "Cleaning up old local backups..."
ls -t /backups/backup_*.sql.gz 2>/dev/null | tail -n +2 | xargs -r rm -f

#Object Storage cleanup (keeping last 7 backups only)
echo "Cleaning up old backups in Object Storage (keeping last 7)..."
oci os object list \
    --bucket-name "$OCI_BUCKET" \
    --namespace "$OCI_NAMESPACE" \
    --prefix "postgres-backups/" \
    --auth instance_principal \
    --query "data[].name" \
    --raw-output \
    | jq -r '.[]' \
    | sort \
    | head -n -7 \
    | while read file; do
        if [ ! -z "$file" ]; then
            oci os object delete \
                --bucket-name "$OCI_BUCKET" \
                --namespace "$OCI_NAMESPACE" \
                --object-name "$file" \
                --auth instance_principal \
                --force
            echo "Deleted old backup: $file"
        fi
    done

echo ""
echo "Backup process completed successfully at $(date)"
echo "=================================================="
echo ""
echo ""