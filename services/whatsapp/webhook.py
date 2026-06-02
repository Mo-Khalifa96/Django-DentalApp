import json
import logging
from django.views import View
from django.conf import settings
from django.utils import timezone
from services.models import Message
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger('whatsapp')


#WhatsApp webhook API view -- for verification and live updates
class WhatsAppWebhookAPIView(View):

    def get(self, request, *args, **kwargs):
        '''
        Meta webhook verification endpoint.
        - Meta sends this once when you register the webhook URL.
        - Echoes back hub.challenge to confirm ownership.
        '''

        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
            logger.info('WhatsApp webhook verified successfully.')
            return HttpResponse(challenge, status=200)

        logger.warning('WhatsApp webhook verification failed.')
        return HttpResponse('Forbidden', status=403)

    def post(self, request, *args, **kwargs):
        '''
        Receives delivery status updates from Meta.
        - Updates Message.status based on provider events.
        - Always returns 200 — Meta will retry indefinitely on any other status.
        '''
        try:
            data = json.loads(request.body)

            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})

                    for status_update in value.get('statuses', []):
                        provider_id = status_update.get('id')
                        new_status  = status_update.get('status')  # sent, delivered, read, failed

                        if provider_id and new_status:
                            updated = Message.objects.filter(
                                providerMessageId=provider_id
                            ).update(
                                status=new_status,
                                lastWebhookAt=timezone.now(),
                            )
                            if updated:
                                logger.info(f'Message {provider_id} status updated to {new_status}.')

        except Exception as exc:
            # Log but always return 200 — never let Meta retry on our processing errors
            logger.error(f'Webhook processing error: {exc}')

        return JsonResponse({'status': 'ok'}, status=200)



#Twilio-based WhatsApp webhook API view
class TwilioWhatsAppWebhookAPIView(View):

    def get(self, request, *args, **kwargs):
        '''
        Meta webhook verification endpoint.
        - Meta sends this once when you register the webhook URL.
        - Echoes back hub.challenge to confirm ownership.
        '''

        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
            logger.info('WhatsApp webhook verified successfully.')
            return HttpResponse(challenge, status=200)

        logger.warning('WhatsApp webhook verification failed.')
        return HttpResponse('Forbidden', status=403)
    
    def post(self, request, *args, **kwargs):
        try:
            message_sid = request.POST.get('MessageSid')
            status = request.POST.get('MessageStatus')  # sent, delivered, read, failed, undelivered

            if message_sid and status:
                # Map Twilio statuses to your model's choices
                status_map = {
                    'sent': 'sent',
                    'delivered': 'delivered',
                    'read': 'read',
                    'failed': 'failed',
                    'undelivered': 'failed',
                }
                mapped_status = status_map.get(status, status)
                Message.objects.filter(providerMessageId=message_sid).update(
                    status=mapped_status,
                    lastWebhookAt=timezone.now(),
                )
                print(f'\n\nTwilio message {message_sid} status: {mapped_status}\n\n')
        except Exception as exc:
            print(f'Webhook processing error: {exc}')
            logger.error(f'Webhook processing error: {exc}')
    
        return JsonResponse({'status': 'ok'}, status=200) 


