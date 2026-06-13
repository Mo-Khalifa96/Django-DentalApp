import logging
from users.models import User
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from services.models import Message
from django_q.models import Schedule
from dateutil.relativedelta import relativedelta
from finances.models import Bill, Transaction, Invoice
from clinic.models import Branch, WaitingRoom, SterilizationLog
from patients.models import Patient, Appointment, PatientRecall


#Initiate logger 
logger = logging.getLogger('django-q')

#YEARLY TASKS 
def cleanup_deleted_payments():
    '''Yearly task to delete soft-deleted payments data if soft-deleted for 10 years or more.'''

    try:
        with transaction.atomic():
            #Calculate the cutoff date (10 years ago)
            ten_years_ago = timezone.now() - relativedelta(years=10)

            #Delete obsolete payments data
            deleted_bills = Bill.all_objects.filter(isDeleted=True, updatedAt__lte=ten_years_ago).delete()
            deleted_transactions = Transaction.all_objects.filter(isDeleted=True, date__lte=ten_years_ago.date()).delete()
            deleted_invoices = Invoice.all_objects.filter(isDeleted=True, createdAt__lte=ten_years_ago).delete()

            #Log task results
            logger.info(f"Bills data cleanup successful. Deleted {deleted_bills[0]} bills.")
            logger.info(f"Transactions data cleanup successful. Deleted {deleted_transactions[0]} transactions.")
            logger.info(f"Invoice data cleanup successful. Deleted {deleted_invoices[0]} invoices.")
    
    except Exception as exc:
        logger.error(f"Error cleaning up payments data: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism


#MONTHLY TASKS 
#Define task to cleanup inactive patients
def cleanup_soft_deleted_data():
    '''Monthly task to delete soft-deleted data if soft-deleted for 1 year or more.'''

    try:
        with transaction.atomic():
            #Calculate the cutoff date (12 months ago)
            one_year_ago = timezone.now() - relativedelta(months=12)
            
            #Delete obsolete data
            deleted_users = User.all_objects.filter(is_deleted=True, updatedAt__lte=one_year_ago).delete()
            deleted_branches = Branch.all_objects.filter(is_deleted=True, updatedAt__lte=one_year_ago).delete()
            deleted_patients = Patient.all_objects.filter(is_deleted=True, updatedAt__lte=one_year_ago).delete()

            #Log task results
            logger.info(f"Users data cleanup successful. Deleted {deleted_users[0]} users.")
            logger.info(f"Branches data cleanup successful. Deleted {deleted_branches[0]} branches.")
            logger.info(f"Patients data cleanup successful. Deleted {deleted_patients[0]} patients.")
            
    except Exception as exc:
        logger.error(f"Error cleaning up soft deleted data: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism


#Define task to clean up sterilization logs
def cleanup_sterilization_logs():
    '''Monthly task to delete sterilization logs older than 1 year.'''

    try:
        with transaction.atomic():
            #Calculate the cutoff date (12 months ago)
            one_year_ago = timezone.now() - relativedelta(months=12)
            
            #Delete sterilization logs older than a year
            deleted_sterilization_logs = SterilizationLog.all_objects.filter(updatedAt__lte=one_year_ago).delete()

            #Log task results
            logger.info(f"Sterilization logs deleted successfully. Deleted {deleted_sterilization_logs[0]} logs.")
            
    except Exception as exc:
        logger.error(f"Error cleaning up sterilization logs: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism


#Define task to clean up patient recalls data
def cleanup_patient_recalls():
    '''Monthly task to delete patient recalls data if status in [contacted, confirmed, declined] and older than 1 year.'''
   
    try:
        with transaction.atomic():
            #Calculate the cutoff date (12 months ago)
            one_year_ago = timezone.now() - relativedelta(months=12)
            
            #Delete patient recall data if not pending/no_answer and older than 1 year
            deleted_recalls = PatientRecall.all_objects.filter(
                Q(dueDate__lte=one_year_ago.date()) | Q(contactedAt__lte=one_year_ago), 
                status__in=['contacted', 'confirmed', 'declined'],
            ).delete()

            #Log task results
            logger.info(f"Patient recalls deleted successfully. Deleted {deleted_recalls[0]} recalls.")
            
    except Exception as exc:
        logger.error(f"Error cleaning up sterilization logs: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism


###################


#WEEKLY TASKS
#Define task to cleanup cancelled appointments
def cleanup_cancelled_appointments():
    '''Weekly task to delete cancelled appointments that's been cancelled for more than a month.'''

    try:
        with transaction.atomic():
            #Calculate the cutoff date (1 months ago)
            one_months_ago = timezone.now() - relativedelta(months=1)
            
            #Delete cancelled appointments older than 1 months
            deleted_appointments = Appointment.all_objects.filter(status='cancelled', updatedAt__lte=one_months_ago).delete()
            
            #Log task results
            logger.info(f"Cancelled appointments deleted successfully. Deleted {deleted_appointments[0]} appointments.")
            
    except Exception as exc:
        logger.error(f"Error cleaning up appointments: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism

#Define task to cleanup waiting room
def cleanup_waiting_room():
    '''Weekly task to delete waiting room entries for past appointments.'''

    try:
        with transaction.atomic():
            #Calculate the cutoff date (1 months ago)
            one_months_ago = timezone.now() - relativedelta(months=1)
            
            #Delete waiting room entries older than 1 months
            deleted_entries = WaitingRoom.all_objects.filter(arrivedAt__lte=one_months_ago).delete()
            
            #Log task results
            logger.info(f"Waiting room entries deleted successfully. Deleted {deleted_entries[0]} entries.")
            
    except Exception as exc:
        logger.error(f"Error cleaning up waiting room entries: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism


#Define task to cleanup whatsapp messages
def cleanup_whatsapp_messages():
    '''Weekly task to delete whatsapp messages.'''
    try:
        with transaction.atomic():
            deleted_messages = Message.objects.filter(
                status__in=['sent', 'delivered', 'read']
            ).delete()
            
            #Log task results
            logger.info(f'Whatsapp messages cleanup successful. Deleted {deleted_messages[0]} messages.')
    
    except Exception as exc:
        logger.error(f"Error cleaning up whatsapp messages: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism


#Define task to cleanup old django-q schedules
def cleanup_past_schedules():
    '''Weekly task to delete old schedules whose scheduled run is past today.'''
    try:
        deleted_schedules = Schedule.objects.filter(
            schedule_type=Schedule.ONCE, next_run__lt=timezone.now(),
        ).delete()
        
        #Log task results
        logger.info(f'Scheduled tasks cleanup successful. Deleted {deleted_schedules[0]} scheduled tasks.')

    except Exception as exc:
        logger.error(f"Error cleaning up scheduled tasks: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism
