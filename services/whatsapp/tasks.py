import logging
from django.http import Http404
from django.conf import settings
from django.utils import timezone
from .whatsapp import WhatsAppClient
from services.models import Message
from django_q.models import Schedule
from patients.models import Appointment
from .exceptions import WhatsAppAPIError 
from datetime import datetime, timedelta
from .utils import (normalize_phone_for_whatsapp,
                    build_custom_message_components,
                    build_reminder_components)


#Initiate logger 
logger = logging.getLogger('whatsapp')


#WHATSAPP-RELATED TASKS 
#Task for sending manual custom (free-form) messages 
def send_whatsapp_message_task(obj, is_instance=False):
    '''
    Task for sending a manually composed, free-form WhatsApp message.
    - Uses the custom_message template, passing the stored message text as the variable.
    - Called asynchronously only as a fallback if the synchronous attempt fails.

    Args:
        obj: takes either a message instance or just the message id.
        is_instance: flag to indicate if it's a model instance or id only.
    
    Returns:
        None
    '''

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
    phone = normalize_phone_for_whatsapp(message.patient.phone)
    
    #build template components -- uses `message` only
    components = build_custom_message_components(message.message)

    try:
        client = WhatsAppClient()
        result = client.send_template_message(
            to_phone=phone,
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


#Task for sending automated 24-hour appointment reminder
def send_appointment_reminder_task(appointment_id: str):
    '''
    ppointment whatsapp reminder task that executes 24 hours prior to a patient appointment.
    - Skips cancelled/completed appointments.
    '''

    try:
        appointment = Appointment.objects.select_related('patient', 'doctor').get(id=appointment_id)
    except (Appointment.DoesNotExist, Http404):
        logger.warning(f'Appointment {appointment_id} not found. Skipping reminder.')
        return

    if appointment.status in ('cancelled', 'completed'):
        logger.info(f'Appointment {appointment_id} is {appointment.status}. Skipping reminder.')
        return

    #get appointment details
    patient = appointment.patient
    doctor_name = appointment.doctor.name
    phone = normalize_phone_for_whatsapp(patient.phone)

    #standardized message for db -- the actual reminder is created by the template stored on Meta
    message_text = f'Reminder for {appointment.patient.name} on {appointment.date} at {appointment.get_time()}'

    #create message instance
    message = Message.objects.create(
        patient=patient,
        appointment=appointment,
        message=message_text,
        templateName=settings.WHATSAPP_REMINDER_TEMPLATE_EN,
        templateLanguage=settings.WHATSAPP_TEMPLATE_LANGUAGE,
        messageType='reminder',
        status='queued',
    )

    #build template components
    components = build_reminder_components(
        patient_name=patient.name,
        doctor_name=doctor_name,
        appointment_date=appointment.date.strftime('%d-%m-%y'),
        appointment_time=appointment.get_time(),
        clinic_name=settings.CLINIC_NAME
    )

    try:
        client = WhatsAppClient()
        result = client.send_template_message(
            to_phone=phone,
            template_name=settings.WHATSAPP_REMINDER_TEMPLATE_EN,
            language_code=settings.WHATSAPP_TEMPLATE_LANGUAGE,
            components=components,
        )
        
        #record to db messaging success and log results
        message.cascade_messaging_results(result=result)
        logger.info(f'Reminder sent for appointment {appointment_id}.')

    except WhatsAppAPIError as exc:
        #record to db messaging failure and log error
        message.cascade_messaging_results(exc=exc)
        logger.error(f'Reminder failed for appointment {appointment_id}: {exc}')
        raise  #raise to re-retry task


#Helper function to schedule appointment reminders 
def schedule_appointment_reminder(appointment):
    '''
    Takes an appointment instance and creates a scheduled task with an appointment whatsapp 
    reminder to be executed 24 hours before the appointment time.
    '''

    
    #dict with the appointment date 
    dt_dict = {'year': appointment.date.year, 'month':appointment.date.month, 
               'day':appointment.date.day, 'hour': appointment.startTime.hour, 
               'minute': appointment.startTime.minute, 'second': 0, 'microsecond':0}
    
    aware_dt = timezone.make_aware(datetime(**dt_dict))
    reminder_date = aware_dt - timedelta(days=1)

    #Create scheduled task for the appointment reminder
    schedule, created = Schedule.objects.get_or_create(
        name=f'Schedule reminder for appointment {appointment.id}',
        defaults={
            'func': 'services.whatsapp.tasks.send_appointment_reminder_task',
            'args': str(appointment.id),
            'schedule_type': Schedule.ONCE,
            'next_run': reminder_date,
            'repeats': 0,
        }
    )

    if created:
        logger.info('Scheduled reminder created successfully.')

    return created
