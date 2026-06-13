import logging
from datetime import timedelta
from django.utils import timezone
from django_q.models import Schedule


#Initialize logger
logger = logging.getLogger('django-q')


#Function to setup scheduled tasks
def setup_scheduled_tasks():

    #Set default first run at 2 AM (low-load time)
    default_first_run = timezone.localtime(timezone.now())
    default_first_run = default_first_run.replace(hour=2, minute=0, second=0, microsecond=0)

    #YEARLY SCHEDULES
    yearly_schedule, created = Schedule.objects.get_or_create(
        name='Cleanup Payments Data Task',
        defaults={
            'func': 'utils.tasks.cleanup_deleted_payments',
            'schedule_type': Schedule.YEARLY,
            'next_run': default_first_run + timedelta(days=365),  #runs every year 2:00 AM
            'repeats': -1   #repeats indefinitely
        }
    )

    if created:
        logger.info(f"Created cleanup task #1: {yearly_schedule.name}")
    else:
        logger.info(f"Task #1 already exists: {yearly_schedule.name}")

    #MONTHLY SCHEDULES
    #Schedule monthly task to cleanup soft-deleted data 
    monthly_schedule, created = Schedule.objects.get_or_create(
        name='Cleanup Soft Deleted Data Task',
        defaults={
            'func': 'utils.tasks.cleanup_soft_deleted_data',
            'schedule_type': Schedule.MONTHLY,
            'next_run': default_first_run + timedelta(days=30),  #runs every month 2:00 AM
            'repeats': -1   #repeats indefinitely
        }
    )

    if created:
        logger.info(f"Created cleanup task #2: {monthly_schedule.name}")
    else:
        logger.info(f"Task #2 already exists: {monthly_schedule.name}")
    
    ####

    #Schedule monthly task to cleanup sterilization logs
    monthly_schedule2, created = Schedule.objects.get_or_create(
        name='Cleanup Sterilization Logs',
        defaults={
            'func': 'utils.tasks.cleanup_sterilization_logs',
            'schedule_type': Schedule.MONTHLY,
            'next_run': default_first_run + timedelta(days=30, minutes=5),  #runs every month 2:05 AM
            'repeats': -1   #repeats indefinitely
        }
    )

    if created:
        logger.info(f"Created cleanup task #3: {monthly_schedule2.name}")
    else:
        logger.info(f"Task #3 already exists: {monthly_schedule2.name}")
    
    ####

    #Schedule monthly task to cleanup patient recalls
    monthly_schedule3, created = Schedule.objects.get_or_create(
        name='Cleanup Patient Recalls',
        defaults={
            'func': 'utils.tasks.cleanup_patient_recalls',
            'schedule_type': Schedule.MONTHLY,
            'next_run': default_first_run + timedelta(days=30, minutes=10),  #runs every month 2:10 AM
            'repeats': -1   #repeats indefinitely
        }
    )

    if created:
        logger.info(f"Created cleanup task #4: {monthly_schedule3.name}")
    else:
        logger.info(f"Task #4 already exists: {monthly_schedule3.name}")
    

    #################


    #WEEKLY SCHEDULES
    #Schedule weekly task to delete cancelled appointments
    weekly_schedule, created = Schedule.objects.get_or_create(
        name='Cleanup Cancelled Appointments Task',
        defaults={
            'func': 'utils.tasks.cleanup_cancelled_appointments',
            'schedule_type': Schedule.WEEKLY,
            'next_run': default_first_run + timedelta(days=7, minutes=15),  #runs every week 2:15 AM
            'repeats': -1})
    
    if created:
        logger.info(f"Created cleanup task #5: {weekly_schedule.name}")
    else:
        logger.info(f"Task #5 already exists: {weekly_schedule.name}")

    ####

    #Schedule weekly task to clean up waiting room
    weekly_schedule2, created = Schedule.objects.get_or_create(
        name='Cleanup Waiting Room Task',
        defaults={
            'func': 'utils.tasks.cleanup_waiting_room',
            'schedule_type': Schedule.WEEKLY,
            'next_run': default_first_run + timedelta(days=7, minutes=20),  #runs every week 2:20 AM
            'repeats': -1})
    
    if created:
        logger.info(f"Created cleanup task #6: {weekly_schedule2.name}")
    else:
        logger.info(f"Task #6 already exists: {weekly_schedule2.name}")

    ####
    
    #Schedule weekly task to delete old whatsapp messages
    weekly_schedule3, created = Schedule.objects.get_or_create(
        name='Cleanup Whatsapp Messages Task',
        defaults={
            'func': 'utils.tasks.cleanup_whatsapp_messages',
            'schedule_type': Schedule.WEEKLY,
            'next_run': default_first_run + timedelta(days=7, minutes=25),  #runs every week 2:25 AM 
            'repeats': -1})
    
    if created:
        logger.info(f"Created cleanup task #7: {weekly_schedule3.name}")
    else:
        logger.info(f"Task #7 already exists: {weekly_schedule3.name}")
    
    ####

    #Schedule weekly task to delete past schedules
    weekly_schedule4, created = Schedule.objects.get_or_create(
        name='Weekly Cleanup Past Schedules',
        defaults={
            'func': 'utils.tasks.cleanup_past_schedules',
            'schedule_type': Schedule.WEEKLY,
            'next_run': default_first_run + timedelta(days=7, minutes=30),  #runs every week 2:30 AM
            'repeats': -1})

    if created:
        logger.info(f"Created cleanup task #8: {weekly_schedule4.name}")
    else:
        logger.info(f"Task #8 already exists: {weekly_schedule4.name}")


