#!/bin/bash

#Set environment 
ENVIRONMENT=${ENVIRONMENT:-local}

WATCH_DIR="."
EXCLUDE_DIRS="(.git|__pycache__|*.pyc|logs|backups|static|media)"

#Set container names based on environment
if [ "$ENVIRONMENT" = "local" ]; then
    SERVICES=("local-web" "local-qcluster" "local-tests") 
    PREFIX="dentaltech"
elif [ "$ENVIRONMENT" = "development" ]; then
    SERVICES=("dev-web" "dev-qcluster")  #"dev-postgres-backup" 
    PREFIX="dentaltech"
else
    SERVICES=("web" "qcluster" "postgres-backup")
    PREFIX="dentaltech"
fi

#Track last synced file and time
LAST_SYNCED_FILE=""
LAST_SYNCED_TIME=0

sync_file() {
    local file="$1"

    if [[ "$file" =~ \.(pyc|swp|tmp)$ ]]; then
        return
    fi

    local project_root="$(pwd)"
    local relative_file="${file#$project_root/}"

    #Skip if same file was synced less than 5 seconds ago
    local current_time=$(date +%s)
    if [[ "$file" == "$LAST_SYNCED_FILE" && $(( current_time - LAST_SYNCED_TIME )) -lt 5 ]]; then
        return
    fi

    LAST_SYNCED_FILE="$file"
    LAST_SYNCED_TIME=$current_time

    echo "-----------"
    echo "Change detected: $relative_file"

    for service in "${SERVICES[@]}"; do
        CONTAINER="$PREFIX-$service"
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
            docker cp "$file" "$CONTAINER:/app/$relative_file" 2>/dev/null && \
                echo "Synced to $CONTAINER"
        fi
    done
    echo "-----------"
    echo "" 
}

echo "Watching for file changes in $WATCH_DIR..."
echo "Press Ctrl+C to stop"
echo ""

#Detect OS and use appropriate watcher
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v fswatch &>/dev/null; then
        echo "fswatch not found. Install it with: brew install fswatch"
        exit 1
    fi

    fswatch -r \
        --exclude "\.git" \
        --exclude "__pycache__" \
        --exclude "\.pytest_cache" \
        --exclude "\.pyc$" \
        --exclude "\.swp$" \
        --exclude "\.tmp$" \
        --exclude "/logs/" \
        --exclude "/backups/" \
        --exclude "/static/" \
        --exclude "/media/" \
        "$WATCH_DIR" | while read file; do
        sync_file "$file"
    done

else
    if ! command -v inotifywait &>/dev/null; then
        echo "inotifywait not found. Install it with: apt-get install inotify-tools"
        exit 1
    fi

    inotifywait -m -r -e modify,create,delete \
        --exclude "$EXCLUDE_DIRS" \
        --format '%w%f' "$WATCH_DIR" | while read file; do
        sync_file "$file"
    done

fi
    
    #Optional: restart containers -- move inside conditionals when ready
    #local:
     # docker restart dentaltech-local-web dentaltech-local-qcluster dentaltech-local-tests
    #dev:
     # docker restart dentaltech-dev-web dentaltech-dev-qcluster
    #prod:
     # docker restart dentaltech-web dentaltech-qcluster 


#HOW TO USE:
 #Add permission first
 # chmod +x ./watch-sync.sh

 #Start watching in background
 # ./watch-sync.sh