import uuid
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

#Custom function to validate uuid input
def validate_uuid(id, version=4):
    '''Helper function to validate incoming uuid.'''
    if id:
        try:
            uuid.UUID(id, version=version)
        except ValueError:
            raise ValidationError({'branchId': 'UUID is invalid.'})
    return id


#Validator for array fields
def validate_not_empty(array):
    if not array:
        raise ValidationError(_('This field cannot be empty.'))
