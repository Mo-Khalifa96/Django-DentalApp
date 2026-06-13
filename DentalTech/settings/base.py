import os 
from pathlib import Path
from dotenv import load_dotenv
from .filters import LogsFormatter, RequestsFilter, DjangoQFilter


#Build paths inside the project like this: BASE_DIR/'sub-dir'
BASE_DIR = Path(__file__).resolve().parents[2]

#Load environment
dotenv_path = BASE_DIR / '.env'
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)   #or consider using python-decouple instead of doing all this to load env variables


#Apps list 
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.postgres',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.humanize',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'users',
    'patients',
    'services',
    'utils.apps.UtilsConfig',
    'clinic.apps.ClinicConfig',
    'finances.apps.FinancesConfig',
    'rest_framework_simplejwt',
    'rest_framework',
    'django_filters',
    'corsheaders',
    'django_q',   
]


#Middlewares
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'services.translation.middleware.LanguageMiddleware',  #Custom language middleware
    #'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


#Root urls
ROOT_URLCONF = 'DentalTech.urls'


#Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


#WSGI app path
WSGI_APPLICATION = 'DentalTech.wsgi.application'


#Default User model 
AUTH_USER_MODEL = 'users.User'

#Set password reset time out 
PASSWORD_RESET_TIMEOUT = 60*60*1  # 1 hours in seconds: 3600

#Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,   
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'users.validators.NumberRequiredValidator',  
    },
    {
        'NAME': 'users.validators.CapitalLetterRequiredValidator',
    }
]


#Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


#Internationalization
#Default language
LANGUAGE_CODE = 'en'

#Accepted languages
LANGUAGES = [
    ('en', 'English'),
    ('ar', 'Arabic'),   #to enable translation, 1) run: 'django-admin makemessages -l ar', 2) edit the file, then 3) run 'django-admin compilemessages'
]

#Path to locale files
LOCALE_PATHS = [    
    BASE_DIR / 'locale',                 
]

#Timezone settings
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True



#Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

#URL to access the uploaded media 
MEDIA_URL = '/media/'

#Root paths for static and media files (as derivative from the base directory)
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATIC_ROOT = os.path.join(BASE_DIR, 'static')



#Django-Q2 Configurations
Q_CLUSTER = {
    'name': 'DentalTech',
    'label': 'System Tasks',  
    'redis': None,  #don't use redis as message broker 
    'orm': 'default',  #use current DB as the message broker
    'poll': 5,    #poll database every 5 seconds (instead of default--microseconds)
    'workers': 1,   #NOTE: adjust this based on your server's CPUs
    'timeout': 90,    #max time a task can take before being killed 
    'retry': 300,     #retry failed tasks after 5 minutes (in seconds)
    'max_attempts': 5,  #retry failed tasks up to 5 times
    'purge': 60*60*24,  #auto-delete task results after 24 hours
    'compress': True,   #allow data compression
    'save_limit': 100,   #limits number of results to 100; auto-delete earlier ones
    'recycle': 25,     #number of tasks a worker can handle before being restarted (more freq refresh saves more RAM)
    'queue_limit': 100,   #maximum number of tasks that can be waiting in the queue at any time
    'ack_failures': True,   #acknoweldge failures
}


#Django REST's settings 
REST_FRAMEWORK = {
            'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
            'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
            'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
            
            #Custom exceptions handler
            'EXCEPTION_HANDLER': 'utils.exceptions.DentalTechExceptionHandler',

            #Custom paginator           
            'DEFAULT_PAGINATION_CLASS': 'utils.pagination.CustomPageNumberPagination',
            'PAGE_SIZE': 20,

            'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle',
                                         'rest_framework.throttling.UserRateThrottle'],
        }



#WHATSAPP SETTINGS 
#flag for whether to enable automated reminders
ENABLE_AUTOMATED_REMINDERS = os.getenv('ENABLE_AUTOMATED_REMINDERS', 'false').lower() == 'true'
#whatsapp credentials and API vars
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.environ.get('WHATSAPP_WEBHOOK_VERIFY_TOKEN')
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v19.0')
#template language 
WHATSAPP_TEMPLATE_LANGUAGE = os.environ.get('WHATSAPP_TEMPLATE_LANGUAGE', 'en_US')
#for custom messages
WHATSAPP_CUSTOM_MESSAGE_TEMPLATE_EN = os.environ.get('WHATSAPP_CUSTOM_MESSAGE_TEMPLATE_EN', 'custom_message_english')
WHATSAPP_CUSTOM_MESSAGE_TEMPLATE_AR = os.environ.get('WHATSAPP_CUSTOM_MESSAGE_TEMPLATE_AR', 'custom_message_arabic')
#for automated reminders
WHATSAPP_REMINDER_TEMPLATE_EN = os.environ.get('WHATSAPP_REMINDER_TEMPLATE_EN', 'appointment_reminder_english')
WHATSAPP_REMINDER_TEMPLATE_AR = os.environ.get('WHATSAPP_REMINDER_TEMPLATE_AR', 'appointment_reminder_arabic')
#other variables 
WHATSAPP_TEST_RECIPIENT = os.environ.get('WHATSAPP_TEST_RECIPIENT')
WHATSAPP_TEST_SENDER = os.environ.get('WHATSAPP_TEST_SENDER')
CLINIC_NAME = os.environ.get('CLINIC_NAME')
#other parameters for testing with twilio 
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_SENDER = os.environ.get('TWILIO_WHATSAPP_SENDER')
WHATSAPP_TEST_RECIPIENT = os.environ.get('WHATSAPP_TEST_RECIPIENT')


#Configure the logger 
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,  
    'formatters': {
        'verbose': {   #used for the logging files 
            '()': LogsFormatter,
            'format': '(%(asctime)s) [%(levelname)s] - \'%(name)s\':  %(message)s',
            'datefmt': '%d/%m/%Y %I:%M %p',
        },
        'simple': {    #to be used for console only
            '()': LogsFormatter,
            'format': '[%(asctime)s] %(levelname)s - \'%(name)s\':  %(message)s',
            'datefmt': '%I:%M %p',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['ignore_requests']  #filter applied globally
        },
        'general_file': {
            'class': 'logging.handlers.RotatingFileHandler',  
            'filename': f'{BASE_DIR}/logs/general.log',
            'filters': ['ignore_requests'],  #filter applied globally
            'formatter': 'verbose',   
            'level': 'DEBUG',   #logs from DEBUG upwards
            'maxBytes': 10*1024*1024,  #10MB max file size
            'backupCount': 5,  
            'encoding': 'utf-8'
        },
        'errors_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'{BASE_DIR}/logs/errors.log',
            'filters': ['ignore_requests'],  #filter applied globally
            'formatter': 'verbose',
            'level': 'ERROR',   #only ERROR and CRITICAL are logged
            'maxBytes': 10*1024*1024,   #10MB max file size
            'backupCount': 5,
            'encoding': 'utf-8'
        }
    },
    'filters': {
        'ignore_requests': {
            '()': RequestsFilter,
        },
        'django_q_filter': {
            '()': DjangoQFilter,
        },
    },
    #configure loggers
    'loggers': {
        #configure root logger
        '': {  
            'handlers': ['console', 'general_file', 'errors_file'],
            'level': 'WARNING',  
            'propagate': False,
        },

        #configure django's logger 
        'django': { 
            'handlers': ['console', 'general_file', 'errors_file'],
            'level': 'WARNING', 
            'propagate': False,
        },

        #configure django's requests logger
        'django.request': {
            'handlers': ['console', 'general_file', 'errors_file'],
            # 'filters': ['ignore_requests'],   #no need - it's activated globally
            'level': 'WARNING',
            'propagate': False,
        },

        #configure logger for core modules
        'patients': {
            'handlers': ['console', 'general_file', 'errors_file'],
            'filters': ['django_q_filter'],
            'level': 'INFO',
            'propagate': False,
        },
        'clinic': {
            'handlers': ['console', 'general_file', 'errors_file'],
            'filters': ['django_q_filter'],
            'level': 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['console', 'general_file', 'errors_file'],
            'filters': ['django_q_filter'],
            'level': 'INFO',
            'propagate': False,
        },
        'finances': {
            'handlers': ['console', 'general_file', 'errors_file'],
            'filters': ['django_q_filter'],
            'level': 'INFO',
            'propagate': False,
        },
        'services': {
            'handlers': ['console', 'general_file', 'errors_file'],
            'filters': ['django_q_filter'],
            'level': 'INFO',
            'propagate': False,
        },

        #configure Django-Q's logger
        'django-q': {   
            'handlers': ['console', 'general_file', 'errors_file'],
            'filters': ['django_q_filter'],
            'level': 'INFO', 
            'propagate': False,
        },

        #configure whatsapp logger 
        'whatsapp': {
            'handlers': ['console', 'general_file', 'errors_file'],
            'level': 'INFO',
            'propogate': False
        },
    },
}


#Check whether to use swagger (remove later and move to dev.py)
ENABLE_SWAGGER = os.getenv('ENABLE_SWAGGER', 'false').lower() == 'true'
if ENABLE_SWAGGER:
    REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'
    INSTALLED_APPS += ['drf_spectacular']
    
    #Swagger settings
    SPECTACULAR_SETTINGS = {
        'TITLE': 'API Endpoints',
        'VERSION': '1.0.0',
        'DESCRIPTION': 'API docs',
        'SERVE_INCLUDE_SCHEMA': False,
        'SECURITY': [
            {'jwtAuth': []}
        ],
        'SWAGGER_UI_SETTINGS': '''{
            filter: true,
            deepLinking: true,
            persistAuthorization: true,
            displayRequestDuration: true,
            syntaxHighlight: true,
            plugins: [
                function (system) {
                    return {
                        fn: {
                            opsFilter: (taggedOps, phrase) => {
                                return taggedOps.filter(
                                    (tagObj, tag) => tag.toLowerCase().indexOf(phrase.toLowerCase()) !== -1
                                );
                            }
                        }
                    }
                }
            ]
        }''',
        'APPEND_COMPONENTS': {
            'securitySchemes': {
                'jwtAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT',
                    'description': 'JWT Authorization token (paste token directly).<br>Format: <access_token> ',
                }
            }
        },
        'TAGS': [
            {'name': 'Auth', 'description': 'JWT Authentication endpoints'},
            {'name': 'Users', 'description': 'User management'},
            {'name': 'Roles and Permissions', 'description': 'Roles and permissions endpoints'},
            {'name': 'Dashboard', 'description': 'Dashboard analytics and metrics'},
            {'name': 'Branches', 'description': 'Branches management'},
            {'name': 'Doctor Schedules', 'description': 'Doctor schedules management'},
            {'name': 'Waiting Room', 'description': 'Waiting room endpoints'},
            {'name': 'Patients', 'description': 'Patients management'},
            {'name': 'Dental Chart', 'description': 'Dental chart endpoints'},
            {'name': 'Appointments', 'description': 'Appointments management'},
            {'name': 'Visit History', 'description': 'Visit history endpoints'},
            {'name': 'Treatment Plans', 'description': 'Patient treatment plans endpoints'},
            {'name': 'Patient Recall', 'description': 'Patient recall endpoints'},
            {'name': 'Payments and Billing', 'description': 'Payment and billing management'},
            {'name': 'Invoices', 'description': 'Invoices management'},
            {'name': 'Procedures', 'description': 'Procedures endpoints'},
            {'name': 'Inventory', 'description': 'Inventory management'},
            {'name': 'Labs', 'description': 'Laboratory management'},
            {'name': 'Lab Orders', 'description': 'Laboratory orders management'},
            {'name': 'Sterilization Log', 'description': 'Sterilization management'},
            {'name': 'WhatsApp', 'description': 'WhatsApp and messaging endpoints'},
        ],
        'COMPONENT_SPLIT_REQUEST': True,
        'SORT_OPERATION_PARAMETERS': False, 
        'POSTPROCESSING_HOOKS': [
            'utils.swagger.response_structure_postprocessing_hook',
        ],
    }

