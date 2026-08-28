import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from patients.models import PatientCoverage


#Initiate logger 
logger = logging.getLogger('django-q')


#Daily task to update patient insurance details
def update_patient_insurance_details_task():
    '''Daily task to check insurance eligibility and update patient insurance details accordingly.'''

    try:
        with transaction.atomic():
            #date today
            today = timezone.localtime(timezone.now())
            today_date = today.date()

            #Update expiring coverages
            #get coverages whose 'effectiveTo' is within 30 days from today
            expiring_coverages = PatientCoverage.objects.filter(
                effectiveTo__isnull=False, effectiveTo__range=(today_date, today_date+timedelta(days=30))
             ).all()
            
            expiring_coverages.update(eligibilityStatus='expiring', 
                                      eligibilityChecked=today.date(),
                                      updatedAt=today
                                    )
            
            #Update expired coverages
            #get coverages past their 'effectiveTo' date
            expired_coverages = PatientCoverage.objects.filter(
                effectiveTo__isnull=False, effectiveTo__lt=today.date()
             ).all()
            
            #update selected coverages
            expired_coverages.update(eligibilityStatus='expired', 
                                       deductibleMet=False,
                                       eligibilityChecked=today.date(),
                                       updatedAt=today
                                    )

    except Exception as exc:
        logger.error(f"Error updating patient insurance details: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism


#Yearly task to update usedYTD on patient insurances
def update_patient_insurance_usedYTD_task():
    '''Yearly task to set usedYTD on patient insurance coverages to 0.'''
    
    try:
        with transaction.atomic():
            #date today
            today = timezone.localtime(timezone.now())

            #get coverages with a set provider
            coverages_to_update = PatientCoverage.objects.filter(provider__isnull=False).all()

            #update selected coverages
            coverages_to_update.update(usedYTD=Decimal('0'), deductibleMet=False, updatedAt=today)
            
    except Exception as exc:
        logger.error(f"Error updating patient insurance usedYTD: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism
