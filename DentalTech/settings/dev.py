import os
from .base import *
from datetime import timedelta

#Specify type of development environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'local')
if ENVIRONMENT == 'local':
    SITE_PROTOCOL = 'http'
    SITE_DOMAIN = 'localhost:8000'
elif ENVIRONMENT == 'development':
    SITE_PROTOCOL = os.getenv('SITE_PROTOCOL')
    SITE_DOMAIN = os.getenv('SITE_DOMAIN')


#Development Security Key
SECRET_KEY = os.environ['DEV_SECRET_KEY']

#DEBUG mode enabled 
DEBUG = True

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')


#Flag to check if application is dockerized or not 
IS_DOCKERIZED = os.getenv('IS_DOCKERIZED', 'false').lower() == 'true'


#Apps and middleware used only in development 
INSTALLED_APPS += [
                    'debug_toolbar', 
                    # 'silk', 
                    ]

MIDDLEWARE += [
               'debug_toolbar.middleware.DebugToolbarMiddleware', 
               # 'silk.middleware.SilkyMiddleware',
               ]


#Internal IPS for Debug Toolbar
INTERNAL_IPS = [
    '127.0.0.1',   
]

#Development database 
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',   
        'NAME': os.environ['DB_NAME'], 
        'USER': os.environ['DB_USER'], 
        'PASSWORD': os.environ['DB_PASSWORD'], 
        'HOST': 'postgres' if IS_DOCKERIZED else 'localhost',
        'PORT': os.environ['DB_PORT'],
        'CONN_MAX_AGE': 60,  
        'CONN_HEALTH_CHECKS': True, 
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=45000',  #45 seconds
        },
    }
}


#Development email settings 
EMAIL_HOST = 'smtp4dev' if IS_DOCKERIZED else 'localhost'
EMAIL_PORT = os.environ['EMAIL_PORT']
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = 'no-reply@DentalTechTeam.com'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'


#Set throttling rate for development
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
                'anon': '400/hour',
                'user': '1000/hour',
            }


#Simple JWT configuration
SIMPLE_JWT = {
            'ACCESS_TOKEN_LIFETIME': timedelta(hours=36),
            'REFRESH_TOKEN_LIFETIME': timedelta(days=14),
            'ROTATE_REFRESH_TOKENS': False,  
            'BLACKLIST_AFTER_ROTATION': False, 
            'UPDATE_LAST_LOGIN': True, 
            'AUTH_HEADER_TYPES': ('Bearer', ), 
        }


#CORS configuration for development 
CORS_ALLOW_ALL_ORIGINS = True

#Disable timezone support in development
# USE_TZ = False 
