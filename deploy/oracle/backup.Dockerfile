# nginx/Dockerfile style — create a new file: docker/backup.Dockerfile
FROM python:3.12-slim

#Set working dir
WORKDIR /app

#Install dependencies for postgres-backup
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gzip \
    bash \
    cron \
    curl \
    jq \
    tzdata \
    locales \
    && pip install --break-system-packages oci-cli \
    && rm -rf /var/lib/apt/lists/*


#Copy relevant scripts
COPY database-backup.sh /app/database-backup.sh
COPY database-backup-cron.sh /app/database-backup-cron.sh
COPY permissions.sh /usr/local/bin/permissions.sh
RUN chmod +x /usr/local/bin/permissions.sh

#Create backup and logs directories
RUN mkdir -p /backups /logs

#Execute permissions.sh
ENTRYPOINT ["permissions.sh"]