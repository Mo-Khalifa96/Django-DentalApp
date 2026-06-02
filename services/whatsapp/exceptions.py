from rest_framework import status
from rest_framework.exceptions import APIException
from django.utils.translation import gettext_lazy as _


#Exception for whatsapp API errors
class WhatsAppAPIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'WHATSAPP_API_ERROR'
    default_detail = _('WhatsApp API error.')

    def __init__(self, message, error_code=None):
        self.error_code = error_code or self.default_code
        super().__init__(detail=message)

    def get_detail(self) -> dict:
        return {
            'message': str(self.detail),
            'code': self.error_code
        }
