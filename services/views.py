from utils.base_views import * 
from django.conf import settings
from rest_framework import status
from django.db import transaction
from services.models import Message
from utils.swagger_utils import extend_schema
from django_q.tasks import async_task
from rest_framework.response import Response
from users.permissions import PatientDataPermissions
from services.whatsapp.exceptions import WhatsAppAPIError 
from services.whatsapp.tasks import send_whatsapp_message_task
from services.whatsapp.twilio import send_twilio_message_task   #TODO - remove successful whatsapp integration
from services.serializers import WhatsappMessageSerializer


#WHATSAPP MESSAGES API VIEWS
#Send whatsapp message API view
@extend_schema(tags=['WhatsApp'])
class SendWhatsAppMessageAPIView(CreateAPIView):
    queryset = Message.objects.all()
    serializer_class = WhatsappMessageSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'send.whatsappMessage'

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        #Serialize incoming data 
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        #Save and get message instance
        message = serializer.save(
            status='queued',
            templateLanguage=settings.WHATSAPP_TEMPLATE_LANGUAGE,
            templateName=settings.WHATSAPP_CUSTOM_MESSAGE_TEMPLATE_EN,
        )

        try:
            #Execute task now and update instance
            send_twilio_message_task(message, is_instance=True)  #TODO - remove after successful whatsapp integration
            #send_whatsapp_message_task(message, is_instance=True)
            
        except WhatsAppAPIError:
            #Sync failed — switch to async retry and return 'pending'
            message.status = 'pending'
            message.save(update_fields=['status'])
            

            #Employ async django-q for the task
            transaction.on_commit(
                lambda: async_task(
                    #'services.whatsapp.tasks.send_whatsapp_message_task',
                    'services.whatsapp.twilio.send_twilio_message_task',  #TODO - remove after successful whatsapp integration
                    str(message.id),  #first parameter to the task function
                    q_options={
                        'task_name': f'WhatsApp Message {message.id}',
                        'max_attempts': 5,  #retry 5 times
                        'retry': 60,
                    }
                )
            )

        #Serialize and send final output response
        serializered_response = self.get_serializer(message).data
        return Response(serializered_response, status=status.HTTP_201_CREATED)

