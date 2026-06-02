import re
from rest_framework.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _


#Custom function to validate phone numbers 
def validate_phone_number(value):
    '''
    Custom validator for phone numbers.\n
    <br>
    Regex explanation: \n
    ^                 - Start of the string \n
    \\+?              - Optional leading plus sign (for international codes) \n 
    [\\d\\s\\-\\(\\)]+ - One or more digits, spaces, hyphens, or parentheses \n 
    \\$                - End of the string \n 
    <br>
    This regex allows for formats like: \n
    +123 456 7890 \n
    (123) 456-7890 \n
    123-456-7890 \n
    1234567890 \n
    +44 20 7946 0958 \n
    '''
    
    phone_regex = r"^\+?[\d\s\-\(\)]+$"

    if not re.fullmatch(phone_regex, value):
        raise ValidationError(
            _("Enter a valid phone number. Only digits, spaces, hyphens, and parentheses allowed."))

#Custom function to validate country code 
def validate_country_code(value):
    '''Validates country code'''
    value = value.strip().replace(' ', '')
    if value.startswith('+'):
        value = '00' + value[1:]
    if not str(value).isdigit():
        raise ValidationError(_("Country code is invalid. Please enter a valid code."))


############


#Custom function to validate file size
def validate_file_size(file):
    '''Validated file/image size.'''
    limit_mb = 5
    if file.size > limit_mb * 1024 * 1024:
        raise ValidationError(_(f"File/Image size should not exceed {limit_mb} MB."))


#Custom function to validate file format
file_validators = [
    validate_file_size,
    FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'pdf']),
]


###########


#FDI tooth numbers validation
FDI_PERMANENT = {str(q * 10 + t) for q in range(1, 5) for t in range(1, 9)}
FDI_DECIDUOUS = {str(q * 10 + t) for q in range(5, 9) for t in range(1, 6)}  #for children
VALID_FDI_TEETH = FDI_PERMANENT | FDI_DECIDUOUS

#Custom function to validate tooth number
def validate_toothNumber(toothNumber):
    '''Validates tooth number according to FDI notation'''
    if toothNumber:
        if not toothNumber.isdigit():
            raise ValidationError(_('Invalid tooth number.'))
        
        if toothNumber not in VALID_FDI_TEETH:
            raise ValidationError(_('Invalid tooth number. Does not comply with FDI notation.'))
