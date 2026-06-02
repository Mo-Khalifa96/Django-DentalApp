from django.urls import path
from services.views import SendWhatsAppMessageAPIView
from services.whatsapp.webhook import WhatsAppWebhookAPIView

#Url patterns
urlpatterns = [
    #Whatsapp messages urls
    path('whatsapp/send/', SendWhatsAppMessageAPIView.as_view(), name='send_whatsapp_reminder'),
    path('whatsapp/webhook/', WhatsAppWebhookAPIView.as_view(), name='whatsapp_webhook')
]