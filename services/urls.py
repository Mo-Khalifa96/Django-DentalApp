from django.urls import path
from services.whatsapp.webhook import WhatsAppWebhookAPIView
from services.views import SendWhatsAppMessageAPIView, ListMessagesHistoryAPIView

#Url patterns
urlpatterns = [
    #Whatsapp messages urls
    path('whatsapp/webhook/', WhatsAppWebhookAPIView.as_view(), name='whatsapp_webhook'),
    path('whatsapp/send/', SendWhatsAppMessageAPIView.as_view(), name='send_whatsapp_reminder'),
    path('whatsapp/<uuid:patientId>/', ListMessagesHistoryAPIView.as_view(), name='list_messages_history')
]