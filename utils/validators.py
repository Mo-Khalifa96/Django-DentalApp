import uuid
from rest_framework.exceptions import ValidationError

def validate_uuid(id, version=4):
    '''Helper function to validate incoming uuid.'''
    if id:
        try:
            uuid.UUID(id, version=version)
        except ValueError:
            raise ValidationError({'branchId': 'UUID is invalid.'})
    return id
