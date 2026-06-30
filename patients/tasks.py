import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from patients.models import PatientCoverage


#Initiate logger 
logger = logging.getLogger('django-q')


#Weekly task to update patient insurance details
def update_patient_insurance_details_task():
    '''Weekly task to check insurance eligibility and update patient insurance details accordingly.'''

    try:
        with transaction.atomic():
            #date today
            today = timezone.localtime(timezone.now())

            #get coverages past their 'effectiveTo' date
            coverages_to_update = PatientCoverage.objects.filter(
                effectiveTo__isnull=False, effectiveTo__lt=today.date()
                ).all()
            
            #update selected coverages
            coverages_to_update.update(eligibilityStatus='expired', 
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
            coverages_to_update.update(usedYTD=Decimal('0'), updatedAt=today)
            
    except Exception as exc:
        logger.error(f"Error updating patient insurance usedYTD: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism
