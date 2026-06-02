import os

#Select environment
ENV = os.environ.get('DJANGO_SETTINGS_MODULE', 'DentalTech.settings.dev')   

#Import settings from the selected environment file
if ENV == 'DentalTech.settings.prod':
    from .prod import *
elif ENV == 'DentalTech.settings.dev':
    from .dev import *
else:
    #fallback or raise an error for unknown settings module
    raise ImportError(f"Unknown DJANGO_SETTINGS_MODULE: {ENV}")

#additional validation 
if os.environ.get('DJANGO_SETTINGS_MODULE') == 'DentalTech.settings.prod':
    if not ALLOWED_HOSTS:
        raise Exception("ALLOWED_HOSTS must be set in production!")
