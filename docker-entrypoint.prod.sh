#!/bin/bash
set -euo pipefail

#Set DJANGO_SETTINGS_MODULE as production settings
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-DentalTech.settings.prod}

ROLE="${SERVICE:-web}"

if [ "$ROLE" = "qcluster" ]; then
    echo "Starting Django-Q2 qcluster (prod)..."
    exec python manage.py qcluster
fi


echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

#Run scheduled-task setup once
echo "Setting up scheduled tasks..."
python manage.py setup_scheduled_tasks || true


# #Identify number of CPU cores on system
# CPU_CORES=$(nproc --all)

# #Rule of thumb: (2 * cores) + 1
# WORKERS=$(( 2 * CPU_CORES + 1 ))


#Gunicorn socket directory
mkdir -p /run/gunicorn

#Start Gunicorn server
echo "Starting Gunicorn (prod) on unix socket..."
exec gunicorn DentalTech.wsgi:application \
    --bind "unix:/run/gunicorn/gunicorn.sock" \
    --workers "${WORKERS:-3}" \
    --timeout 60 \
    --graceful-timeout 30 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level info