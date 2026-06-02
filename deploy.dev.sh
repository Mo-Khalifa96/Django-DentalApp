#!/bin/bash
set -e

echo "Starting development deployment..."

#Capture script args
SCRIPT_ARGS=("$@")

#Save pre-deployment commit
PRE_DEPLOY_COMMIT=$(git rev-parse HEAD)

#Backup current nginx config for rollback
cp nginx/nginx.conf nginx/nginx.conf.backup 2>/dev/null || true


#Generate nginx configs from templates in /nginx/
#load env variables
set -a
source .env
set +a

#export domain name to nginx configs
envsubst '${SITE_DOMAIN}' < nginx/http.template.conf > nginx/http.conf
envsubst '${SITE_DOMAIN}' < nginx/https.template.conf > nginx/https.conf


#Rollback function to return to last functional state upon failure
rollback() {
    echo "Deployment failed - Rolling back to previous state..."
    if [ -f nginx/nginx.conf.backup ]; then
        cp nginx/nginx.conf.backup nginx/nginx.conf
        docker compose -f docker-compose.dev.yml exec -T nginx nginx -s reload 2>/dev/null || true
        echo "Nginx rollback successful. Site should be accessible with previous configuration."
    fi

    #You can also rollback git changes as well
    if [[ "${SCRIPT_ARGS[*]}" == *"--enable-rollback"* ]]; then
        echo "Git rollback applied."
        echo ""
        #Rollback git to pre-deployment commit
        git reset --hard $PRE_DEPLOY_COMMIT        
        #Rebuild and restart with old code
        docker compose -f docker-compose.dev.yml --profile dev build --build-arg ENVIRONMENT=development
        docker compose -f docker-compose.dev.yml --profile dev up -d --no-build postgres web qcluster smtp4dev postgres-backup
        echo "Git rollback successful. Reverted back to old code."
    fi
    echo ""
    echo "Rollback completed."
    echo ""

}
trap rollback ERR

#Function to switch nginx configuration
switch_nginx_config() {
    local config_type=$1
    echo "Switching to nginx $config_type configuration..."
    if [ "$config_type" = "http" ]; then
        cp nginx/http.conf nginx/nginx.conf
    elif [ "$config_type" = "https" ]; then
        cp nginx/https.conf nginx/nginx.conf
    else
        echo "Invalid config type: $config_type"
        exit 1
    fi
}


#Pull new code
if [[ "${SCRIPT_ARGS[*]}" == *"--enable-rollback"* ]]; then
    echo "Pulling latest code before building..."
    git pull origin main || \
    { git reset --hard && git clean -fd && git pull origin main; } || \
    { git pull --rebase origin main && git pull origin main; }
fi 


#Build app images
if [[ "${SCRIPT_ARGS[*]}" == *"--rebuild"* && "${SCRIPT_ARGS[*]}" == *"--no-cache"* ]]; then
    echo "Building cloud development image with no cache..."
    docker compose -f docker-compose.dev.yml --profile dev build --no-cache --build-arg ENVIRONMENT=development
elif [[ "${SCRIPT_ARGS[*]}" == *"--rebuild"* ]] || ! docker images --format "{{.Repository}}" | grep -qE "(dental-tech|dentaltech|django-dentalapp)"; then
    echo "Building cloud development image with development dependencies..."
    docker compose -f docker-compose.dev.yml --profile dev build --build-arg ENVIRONMENT=development
else
    echo "Images already exist, skipping build..."
fi
echo ""


#Start with HTTP-only configuration
switch_nginx_config "http"


echo "Starting app services..."
docker compose -f docker-compose.dev.yml --profile dev up -d postgres web qcluster smtp4dev postgres-backup


echo "Waiting for web service to be healthy..."
timeout 180 bash -c 'until docker compose -f docker-compose.dev.yml ps web | grep -q "healthy"; do
    echo "Still waiting for web service...";
    sleep 5;
done' || {
    echo "Web service failed. Stopping deployment..."
    exit 1
}


echo ""
echo "Now starting nginx..."
docker compose -f docker-compose.dev.yml up -d nginx

echo "Waiting for nginx to be ready..."
timeout 90 bash -c 'until docker compose -f docker-compose.dev.yml ps nginx | grep -q "Up"; do
    echo "Still waiting for nginx...";
    sleep 5;
done' || {
    echo "Nginx failed to start. Stopping deployment..."
    exit 1   #exit if web isn't healthy for longer than 90 seconds
}

echo "Testing nginx configuration..."
docker compose -f docker-compose.dev.yml exec -T nginx nginx -t


echo "Creating ACME challenge directory..."
docker compose -f docker-compose.dev.yml exec -T nginx sh -c 'mkdir -p /var/www/certbot/.well-known/acme-challenge'


echo "Testing basic HTTP access..."
echo ""
if ! curl -f --connect-timeout 10 --max-time 30 http://${SITE_DOMAIN}/health/; then
    echo "HTTP access test failed! Stopping deployment..."
    exit 1   #exit if HTTP access fails
fi
echo ""
echo ""


echo "Creating ACME test file..."
docker compose -f docker-compose.dev.yml exec -T nginx sh -c 'echo "test" > /var/www/certbot/.well-known/acme-challenge/test'

echo "Testing ACME challenge path..."
if ! curl -f --connect-timeout 10 --max-time 30 http://${SITE_DOMAIN}/.well-known/acme-challenge/test; then
    echo "ACME challenge path not accessible! Stopping deployment..."
    exit 1
fi


echo ""
echo "Checking if certificates need renewal..."
if docker compose -f docker-compose.dev.yml run --rm --entrypoint certbot certbot certificates 2>/dev/null | grep -q "INVALID\|will expire"; then
    echo "Certificates need renewal or don't exist"
    RENEWAL_FLAG="--force-renewal"
else
    echo "Certificates are valid, attempting normal renewal"
    RENEWAL_FLAG=""
fi

echo "Issuing/renewing certificates..."
docker compose -f docker-compose.dev.yml run --rm --entrypoint certbot certbot certonly \
    --webroot --webroot-path=/var/www/certbot \
    --email ${CERTBOT_EMAIL} \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    --keep-until-expiring \
    $RENEWAL_FLAG \
    -d ${SITE_DOMAIN} -d www.${SITE_DOMAIN}
echo "Certificates obtained."


echo "Verifying certificates..."
if ! docker compose -f docker-compose.dev.yml exec -T nginx ls /etc/letsencrypt/live/${SITE_DOMAIN}/ >/dev/null 2>&1; then
    echo "Certificates not found! Cannot switch to HTTPS. Stopping deployment..."
    exit 1
fi
echo ""


# echo "Processing CORS variables in HTTPS config..."
# CORS_ALLOWED_ORIGINS="$CORS_ALLOWED_ORIGINS" envsubst '$CORS_ALLOWED_ORIGINS' < nginx/https.conf > nginx/https.conf.tmp
# mv nginx/https.conf.tmp nginx/https.conf


#Switch to https
switch_nginx_config "https"

echo "Testing new HTTPS configuration..."
docker compose -f docker-compose.dev.yml exec -T nginx nginx -t

echo "Reloading nginx with HTTPS configuration..."
docker compose -f docker-compose.dev.yml exec -T nginx nginx -s reload
sleep 5


echo "Testing HTTPS access..."
echo ""
if ! curl -f --connect-timeout 10 --max-time 30 https://${SITE_DOMAIN}/health/; then
    echo "HTTPS access test failed! Check your certificates and nginx config. Stopping deployment..."
    exit 1  #exits if HTTPS access fails after nginx is loaded
fi
echo ""
echo ""


#Start certbot renewal loop
echo "Starting certbot renewal container..."
docker compose -f docker-compose.dev.yml up -d certbot
echo ""


#Clean up backup file on success
rm -f nginx/nginx.conf.backup

#Declare deployment success 
echo "Development deployment completed successfully!"


###########

#To run, make sure you have permission:
  # chmod +x deploy.dev.sh
  # ./deploy.dev.sh (assuming you're in the root directory)
    

#For force rebuild, run:
  # ./deploy.dev.sh --rebuild

#For building without cache:
  # ./deploy.dev.sh --rebuild --no-cache

#For enabling git rollback (revert to pre-deployment state):
  # ./deploy.dev.sh --enable-rollback  # or,
  # ./deploy.dev.sh --rebuild --enable-rollback  # or,
  # ./deploy.dev.sh --rebuild --no-cache --enable-rollback
