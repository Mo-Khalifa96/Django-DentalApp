import os 
from .base import * 
import dj_database_url
from datetime import timedelta


#Production Security Key
SECRET_KEY = os.environ['PROD_SECRET_KEY']  

#Debugging mode off
DEBUG = False

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

SITE_PROTOCOL = os.getenv('SITE_PROTOCOL')
SITE_DOMAIN = os.getenv('SITE_DOMAIN')


#Database for production
DATABASES = {
    'default': {
        **dj_database_url.config(),   #configure database from the DATABASE_URL env variable
        
        #Database health checks
        'CONN_MAX_AGE': 60,  
        'CONN_HEALTH_CHECKS': True, 
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=45000',  #45 seconds
        },
      }  
}


#Email Settings for production
EMAIL_HOST = os.environ['BREVO_SMTP_SERVER']
EMAIL_HOST_USER = os.environ['BREVO_SMTP_USER']
EMAIL_HOST_PASSWORD = os.environ['BREVO_SMTP_PASSWORD']
EMAIL_PORT = os.environ['BREVO_SMTP_PORT']
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'no-reply@DentalTechTeam.com'  
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'


#Set throttling rate for production
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
                'anon': '50/hour',
                'user': '1000/hour',
            }

#JWT's settings for authentication 
SIMPLE_JWT = {
            'ACCESS_TOKEN_LIFETIME': timedelta(minutes=45),
            'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
            'ROTATE_REFRESH_TOKENS': False,  
            'BLACKLIST_AFTER_ROTATION': False,
            'UPDATE_LAST_LOGIN': True, 
            'AUTH_HEADER_TYPES': ('Bearer', ), 
        }


#CORS Settings
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')


#Security configurations 
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_SECONDS = 31536000
#*new*
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
