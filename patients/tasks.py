import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from patients.models import PatientCoverage
from django.db.models import F, Case, When, Value, DateField, BooleanField


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
            coverages = PatientCoverage.objects.exclude(
                eligibilityStatus__in=['expired', 'limit_reached']
            ).all()

            #get coverages whose 'effectiveTo' is within 30 days from today
            expiring_coverages = coverages.filter(
                effectiveTo__isnull=False, effectiveTo__range=(today_date, today_date+timedelta(days=30))
             ).all()
            
            #update selected coverages
            expiring_coverages.update(eligibilityStatus='expiring', 
                                      eligibilityChecked=today.date(),
                                      updatedAt=today
                                    )
            
            #Update expired coverages
            #get coverages past their 'effectiveTo' date
            expired_coverages = coverages.filter(
                effectiveTo__isnull=False, effectiveTo__lt=today.date()
             ).all()
            
            #update selected coverages
            expired_coverages.update(eligibilityStatus='expired', 
                                     deductibleMet=None,
                                     eligibilityChecked=today.date(),
                                     updatedAt=today
                                    )
            
            #Update maxed out coverages
            maxed_out_coverages = coverages.filter(
                annualMax__isnull=False, usedYTD__isnull=False, usedYTD__gte=F('annualMax'),
            ).all()

            #update selected coverages
            maxed_out_coverages.update(eligibilityStatus='limit_reached',
                                       deductibleMet=None,
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
            coverages_to_update = PatientCoverage.objects.filter(provider__isnull=False)

            #update selected coverages 
            coverages_to_update.update(
                updatedAt=today,
                usedYTD=Decimal('0'),
                eligibilityStatus=Case(
                    When(eligibilityStatus='limit_reached', then=Value('active')),
                    default=F('eligibilityStatus')
                ),
                eligibilityChecked=Case(
                    When(eligibilityStatus='limit_reached', then=Value(today.date())),
                    default=F('eligibilityChecked'),
                    output_field=DateField()
                ),
                deductibleMet=Case(   #when coverage is 100%, deductible is always True
                    When(coveragePercent=100, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField()
                )
            )
            
    except Exception as exc:
        logger.error(f"Error updating patient insurance usedYTD: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism

