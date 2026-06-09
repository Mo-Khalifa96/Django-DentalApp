import uuid 
from django.db import models
from django.db import transaction
from django.utils import timezone
from patients.models import Patient, Appointment


#MESSAGES MODEL
class Message(models.Model):
    class MessageStatusChoices(models.TextChoices):
        QUEUED = 'queued'
        PENDING = 'pending'
        SENT = 'sent'
        DELIVERED = 'delivered'
        READ = 'read'
        FAILED = 'failed'

    class MessageTypeChoices(models.TextChoices):
        REMINDER = 'reminder'
        RECALL = 'recall'
        CUSTOM = 'custom'


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to the Patient model (i.e., many messages, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_reminders', on_delete=models.CASCADE, db_index=True)

    #Many-to-One relationship to the Appointment model (i.e., many messages, one appointment)
    appointment = models.ForeignKey(Appointment, related_name='appointment_reminders', on_delete=models.DO_NOTHING, db_index=True) 

    #main model fields
    message = models.TextField()
    messageType = models.CharField(max_length=25, choices=MessageTypeChoices.choices, blank=True, null=True)
    status = models.CharField(max_length=25, choices=MessageStatusChoices.choices, default=MessageStatusChoices.QUEUED)  #change to 'sent' when successfully sent
    sentAt = models.DateTimeField(blank=True, null=True)  #add time when actually sent!

    #fields to track message sending
    providerMessageId = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    templateLanguage = models.CharField(max_length=20, blank=True, null=True)
    templateName = models.CharField(max_length=255, blank=True, null=True)
    errorMessage = models.TextField(blank=True, null=True)
    errorCode = models.CharField(max_length=50, blank=True, null=True)
    lastWebhookAt = models.DateTimeField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Messages'
        verbose_name_plural = 'Messages'
        ordering = ['-sentAt']
    
    def cascade_messaging_results(self, result=None, exc=None):
        '''Updates relevant fields based on message sending results.'''
        if not exc:  #if message sent successfully...
            #update message
            self.status = 'sent'
            self.sentAt = timezone.localtime(timezone.now())
            self.providerMessageId = result.get('message_id')
            self.save(update_fields=['status', 'sentAt', 'providerMessageId'])
        else:   #if message sending failed...
            #update to failed 
            self.status = 'failed'
            self.errorMessage = str(exc)
            self.errorCode = str(exc.error_code) if exc.error_code else None
            self.save(update_fields=['status', 'errorMessage', 'errorCode']) 
