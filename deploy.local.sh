#!/bin/bash
set -e

echo "Starting local deployment..."

#Capture script args
SCRIPT_ARGS=("$@")


#Build app images
if [[ "${SCRIPT_ARGS[*]}" == *"--rebuild"* && "${SCRIPT_ARGS[*]}" == *"--no-cache"* ]]; then
    echo "Building local development image with no cache..."
    docker compose -f docker-compose.local.yml --profile local build --no-cache --build-arg ENVIRONMENT=local
elif [[ "${SCRIPT_ARGS[*]}" == *"--rebuild"* ]] || ! docker images --format "{{.Repository}}" | grep -qE "(dental-tech|dentaltech)"; then
    echo "Building local development image with dev dependencies..."
    docker compose -f docker-compose.local.yml --profile local build --build-arg ENVIRONMENT=local
else
    echo "Images already exist, skipping build..."
fi


#Local development stack (no SSL/nginx by default)
echo "Starting local development stack..."
docker compose -f docker-compose.local.yml --profile local up -d postgres web qcluster smtp4dev tests

echo "Local deployment started. Access at http://localhost:8000"


#To run, make sure you have permission:jcf
    # chmod +x deploy.local.sh
    # ./deploy.local.sh (assuming you're in the root directory)
    
#For force rebuild, run:
    # ./deploy.local.sh --rebuild

#or (for building without cache):
    # ./deploy.local.sh --rebuild --no-cache
