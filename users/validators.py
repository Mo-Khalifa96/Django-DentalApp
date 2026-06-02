import re
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


#Password validation classes 
class NumberRequiredValidator:
    def validate(self, password, user=None):
        if not re.search(r'\d', password):
            raise ValidationError(_('Password must contain at least one digit.'), 
                                  code='password_no_number')

    def get_help_text(self):
        return _('Your password must contain at least one digit [0-9].')

class CapitalLetterRequiredValidator:
    def validate(self, password, user=None):
        if password == password.lower():
            raise ValidationError(_('Password must contain at least one capital letter.'), 
                                  code='password_no_capital_letter')

    def get_help_text(self):
        return _('Your password must contain at least one capital letter [A-Z].')


#Validation Methods 
#Custom method to validate image size 
def validate_image_size(value): 
    filesize = value.size
    limit_mb = 5  # Maximum file size (5MB)
    if filesize > limit_mb * 1024 * 1024:
        raise ValidationError(_(f"Photo size should not exceed {limit_mb} MB."))
