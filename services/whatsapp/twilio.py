import logging
from django.http import Http404
from django.conf import settings
from .exceptions import WhatsAppAPIError


#Initialize logger
logger = logging.getLogger('whatsapp')


#Twilio WhatsApp client (for testing)
class TwilioWhatsAppClient:
    '''WhatsApp client using Twilio — for sandbox testing.'''

    def __init__(self):
        from twilio.rest import Client
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.sender_phone = settings.TWILIO_WHATSAPP_SENDER

    def send_template_message(self, recipient_phone, template_name, language_code, components=None):
        '''
        Send a WhatsApp message via Twilio sandbox.
        
        Note: Twilio sandbox does not use Meta templates — it sends free-form text.
        The components are used to build the message body instead.
        
        Args:
            recipient_phone:      recipient in format 'whatsapp:+2001012345678'
            template_name: ignored in sandbox, used for logging only
            language_code: ignored in sandbox
            components:    list of component dicts — body parameters are extracted
        
        Returns:
            dict with 'message_id'
        
        Raises:
            WhatsAppAPIError
        '''
        
        #In development, route to test recipient
        if settings.DEBUG and settings.WHATSAPP_TEST_RECIPIENT:
            recipient_phone = settings.WHATSAPP_TEST_RECIPIENT
            logger.debug(f'DEBUG mode: routing to test recipient {recipient_phone}')

        #Format recipient for Twilio if not already formatted
        if not recipient_phone.startswith('whatsapp:'):
            recipient_phone = f'whatsapp:+{recipient_phone}'

        #Build message body from components
        body = self._build_body_from_components(components, template_name)

        try:
            message = self.client.messages.create(
                from_=self.sender_phone,
                to=recipient_phone,
                body=body,
            )
            logger.info(f'Twilio WhatsApp message sent. SID: {message.sid}')
            return {'message_id': message.sid}

        except Exception as exc:
            logger.error(f'Twilio Error: {exc}')
            raise WhatsAppAPIError(str(exc))

    def _build_body_from_components(self, components, template_name):
        '''Extract text parameters from components and build a readable message body.'''
        if not components:
            return f'Message from {template_name}'

        params = []
        for component in components:
            if component.get('type') == 'body':
                for param in component.get('parameters', []):
                    if param.get('type') == 'text':
                        params.append(param['text'])

        if template_name == 'appointment_reminder' and len(params) >= 4:
            #parameters: [patient_name, date, time, doctor_name, clinic_name]
            return (
                f'Hello {params[0]}, this is a reminder that you have an appointment '
                f'on {params[1]} at {params[2]}. '
                f'Please contact us if you need to reschedule. '
                f'— {params[3]}'
            )

        if template_name and params:
            return ' '.join(params)

        return f'Message: {template_name}'



#Task for sending manual custom -- adjusted for twilio
def send_twilio_message_task(obj, is_instance=False):
    '''The same task as send_whatsapp_message_task() but adjusted for twilio.'''
    from .utils import build_custom_message_components
    from services.models import Message

    if not is_instance:
        message_id = obj
        try:
            message = Message.objects.select_related('patient', 'appointment__doctor').get(id=message_id)
        except (Message.DoesNotExist, Http404):
            logger.error(f'Message {message_id} not found. Skipping.')
            return
    else:
        message = obj  #use instance directly

    #normalize phone number for whatsapp
    phone = _format_phone(message.patient.phone)
    
    #build template components -- uses `message` only
    components = build_custom_message_components(message.message)

    try:
        client = TwilioWhatsAppClient()
        result = client.send_template_message(
            recipient_phone=phone,
            template_name=settings.WHATSAPP_CUSTOM_MESSAGE_TEMPLATE_EN,
            language_code=settings.WHATSAPP_TEMPLATE_LANGUAGE,
            components=components,
        )

        #record to db messaging success and log results
        message.cascade_messaging_results(result=result)
        logger.info(f'Custom message {message.id} sent successfully.')

    except WhatsAppAPIError as exc:
        #record to db messaging failure and log error
        message.cascade_messaging_results(exc=exc)
        logger.error(f'Custom message {message.id} failed: {exc}')
        raise  #raise to re-retry task


def _format_phone(phone):
    '''Format phone for the active WhatsApp provider.'''
    from services.whatsapp.utils import normalize_phone_for_whatsapp
    phone = normalize_phone_for_whatsapp(phone)
    if not phone.startswith('whatsapp:'):
        phone = f'whatsapp:+{phone}'
    return phone 


#Test directly in shell:
# Run in Django shell
# python manage.py shell

# from django.conf import settings
# from services.whatsapp.twilio import TwilioWhatsAppClient

# client = TwilioWhatsAppClient()
# result = client.send_template_message(
#     recipient_phone=settings.WHATSAPP_TEST_RECIPIENT,
#     template_name='appointment_reminder',
#     language_code='en_US',
#     components=[{
#         'type': 'body',
#         'parameters': [
#             {'type': 'text', 'text': 'Test Patient'},
#             {'type': 'text', 'text': '20-05-2026'},
#             {'type': 'text', 'text': '10:00 AM'},
#             {'type': 'text', 'text': 'Dr. Hassan'},
#             {'type': 'text', 'text': 'Test Clinic'},
#         ]
#     }]
# )
# print(result)