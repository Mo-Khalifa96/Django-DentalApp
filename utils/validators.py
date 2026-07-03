import uuid
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

#Custom function to validate uuid input
def validate_uuid(id, keyname=None):
    '''Helper function to validate incoming uuid.'''
    if id:
        try:
            uuid.UUID(id, version=4)
        except (ValueError, AttributeError):
            key = (keyname if keyname else 'uuid')
            raise ValidationError({key: 'UUID is invalid.'})
    return id
