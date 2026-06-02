import requests
import logging
from django.conf import settings
from .exceptions import WhatsAppAPIError
from .utils import normalize_phone_for_whatsapp

#Initialize logger
logger = logging.getLogger('whatsapp')


#Meta WhatsApp client (for production)
class WhatsAppClient:
    '''Client for the WhatsApp Business Cloud API.'''

    BASE_URL = 'https://graph.facebook.com'

    def __init__(self):
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.api_version = settings.WHATSAPP_API_VERSION
        self.url = f'{self.BASE_URL}/{self.api_version}/{self.phone_number_id}/messages'

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }

    def send_template_message(self, to_phone, template_name, language_code, components=None):
        '''
        Send a WhatsApp template message.

        Args:
            to_phone: recipient in international format without + (e.g. '2001012345678').
            template_name: approved template name.
            language_code: template language code (e.g. 'en_US').
            components: list of template variable component dicts.

        Returns:
            dict with 'message_id'

        Raises:
            WhatsAppAPIError
        '''

        #In development, route all messages to the test recipient
        if settings.DEBUG and settings.WHATSAPP_TEST_RECIPIENT:
            to_phone = normalize_phone_for_whatsapp(settings.WHATSAPP_TEST_RECIPIENT)
            logger.debug(f'DEBUG mode: routing message to test recipient {to_phone}')

        payload = {
            'messaging_product': 'whatsapp',
            'to': to_phone,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language_code},
            }
        }

        if components:
            payload['template']['components'] = components

        try:
            #send request with the payload to meta
            response = requests.post(self.url, headers=self._headers(), json=payload, timeout=30)
            data = response.json()

            if response.status_code != 200 or 'error' in data:
                error = data.get('error', {})
                msg = error.get('message', 'Unknown WhatsApp API error')
                code = error.get('code')
                logger.error(f'WhatsApp API Error [{code}]: {msg}')
                raise WhatsAppAPIError(msg, error_code=code)

            message_id = data.get('messages', [{}])[0].get('id')
            logger.info(f'WhatsApp message sent. Provider ID: {message_id}')

            #return message_id as result
            return {'message_id': message_id}

        except requests.RequestException as exc:
            logger.error(f'Network Error: {exc}')
            raise WhatsAppAPIError(f'Network Error: {exc}')
