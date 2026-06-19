
from services.models import Message
from rest_framework import serializers
from patients.models import Patient, Appointment
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField


#WHATSAPP MESSAGES SERIALIZERS
#Whatsapp Messages Serializer
class WhatsappMessageSerializer(serializers.ModelSerializer):
    messageId = serializers.PrimaryKeyRelatedField(source='id', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())
    appointmentId = serializers.PrimaryKeyRelatedField(source='appointment', queryset=Appointment.objects.all())
    type = TranslatedChoiceField(source='messageType', choices=Message.MessageTypeChoices.choices, 
                                 required=False, allow_blank=False, allow_null=True)

    class Meta:
        model = Message
        fields = ['messageId', 'patientId', 'appointmentId', 'message', 'type', 'status', 'sentAt']
        read_only_fields = ['messageId', 'status', 'sentAt']
    
    def validate(self, data):
        message_type = data.get('messageType')
        if not message_type:
            data['messageType'] = 'custom'
        return data
