#!/bin/bash

#Automated script version 
set -e

echo "Starting certificate renewal check..."

certbot renew --quiet --webroot --webroot-path=/var/www/certbot

if [ $? -eq 0 ]; then
    echo "Certificate renewal completed"
else
    echo "Certificate renewal failed"
    exit 1
fi



#Old / Manual version
# set -e

# cd /home/ubuntu/Django-system-app

# echo "Starting certificate renewal check..."

# #Try to renew certificates (certbot only renews if < 30 days left)
# docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm certbot renew --quiet

# #Check if renewal was successful and reload nginx
# if [ $? -eq 0 ]; then
#     echo "Certificate renewal check completed"
#     echo "Reloading nginx..."
#     docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
#     echo "Nginx reloaded successfully"
# else
#     echo "Certificate renewal failed"
#     exit 1
# fi


# Automate script for certs renewal with crontab:

    # #Edit crontab
    # sudo crontab -e   <--

    # #Runs twice daily at 12:00 and 00:00)
    # 0 0,12 * * * /home/ubuntu/Django-system-app/renew-certs.sh >> /var/log/certbot-renewal.log 2>&1   <--
