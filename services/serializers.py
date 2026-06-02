
from services.models import Message
from rest_framework import serializers
from patients.models import Patient, Appointment
from django.utils.translation import gettext_lazy as _


#WHATSAPP MESSAGES SERIALIZERS
#Whatsapp Messages Serializer
class WhatsappMessageSerializer(serializers.ModelSerializer):
    messageId = serializers.PrimaryKeyRelatedField(source='id', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())
    appointmentId = serializers.PrimaryKeyRelatedField(source='appointment', queryset=Appointment.objects.all())
    type = serializers.CharField(source='messageType', required=False, allow_blank=True)

    class Meta:
        model = Message
        fields = ['messageId', 'patientId', 'appointmentId', 'message', 'type', 'status', 'sentAt']
        read_only_fields = ['messageId', 'status', 'sentAt']
