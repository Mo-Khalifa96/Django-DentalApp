from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Sum
from django.dispatch import receiver
from patients.models import PatientCoverage
from django.db.models.functions import Coalesce
from django.db.models.signals import m2m_changed
from finances.models import Bill, Transaction, Installment
from django.db.models.signals import pre_save, post_save, pre_delete


#Signal for updating visit's cost upon billing
@receiver(m2m_changed, sender=Bill.visits.through)
def update_visit_costs(sender, instance, action, pk_set, **kwargs):
    '''
    Signal to calculate visit cost after bills are issued.\n
    Helps when a several bills are issued on the same day (i.e. for a single visit).
    '''
    
    if action in ('post_add', 'post_remove', 'post_clear'):
        #calculate cost for each affected visit
        for visit in instance.visits.all():
            visit.cost = Bill.objects.filter(visits=visit)\
                .aggregate(totalCost=Coalesce(Sum('totalAmount'), Decimal('0')))['totalCost']
            #save cost update
            visit.save(update_fields=['cost'])


#or, if you want to set visit costs to 0 after being removed 
# while editing Bill
# @receiver(m2m_changed, sender=Bill.visits.through)
# def update_visit_costs(sender, instance, action, pk_set, **kwargs):
#     if action == 'pre_clear':
#         #capture visits before they are removed
#         instance._visits_to_update = list(instance.visits.values_list('id', flat=True))

#     elif action == 'post_clear':
#         #recalculate cost for visits that were just removed
#         visit_ids = getattr(instance, '_visits_to_update', [])
#         for visit in Visit.objects.filter(id__in=visit_ids):
#             visit.cost = Bill.objects.filter(visits=visit)\
#                 .aggregate(totalCost=Coalesce(Sum('totalAmount'), Decimal('0')))['totalCost']
#             visit.save(update_fields=['cost'])

#     elif action in ('post_add', 'post_remove'):
#         for visit in instance.visits.all():
#             visit.cost = Bill.objects.filter(visits=visit)\
#                 .aggregate(totalCost=Coalesce(Sum('totalAmount'), Decimal('0')))['totalCost']
#             visit.save(update_fields=['cost'])


##########


#Signal to capture transaction method on updated instance 
@receiver(pre_save, sender=Transaction)
def track_transaction_method_changes(sender, instance, **kwargs):
    if not instance._state.adding:  #update
        try:
            prev = Transaction.all_objects.get(id=instance.id)
            instance._prev_method = prev.method
            instance._prev_status = prev.status
        except:
            instance._prev_method = None
            instance._prev_status = None


#Signal for updating transaction-related data upon saving (bill/visit/installments/insurance)
@receiver([post_save, pre_delete], sender=Transaction)
def update_transaction_aggregates(sender, instance, **kwargs):
    #Determine type of signal/operation
    is_deletion = kwargs.get('signal') is pre_delete
    # #make sure you have up-to-date data (remove caching)
    # instance.patient._state.fields_cache.pop('patient_insurance', None)

    #Handle transaction deletion (soft-delete & hard delete) and refunds
    exclude_ids = []
    if is_deletion or instance.isDeleted or instance.status == 'refunded':
        #remove installment's paidAt and transaction
        Installment.objects.filter(transaction_id=instance.id)\
         .update(paidAt=None, transaction=None)

        #add transaction id to exclude
        exclude_ids.append(instance.id)

    #Update bill's `totalPaid`
    if instance.bill:
        #handle deposit bills separately -- don't update amount
        if instance.type == 'deposit':
            _handle_deposit_refunds(instance)
        else:
            #update bill's total paid
            total_paid = Transaction.objects.completed().filter(bill=instance.bill)\
                .exclude(Q(id__in=exclude_ids)
                ).aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
            )['total_paid']
            instance.bill.totalPaid = total_paid
            instance.bill.save(update_fields=['totalPaid'])
        
            #update installment plan's total paid if bill has one
            if instance.bill.installmentPlan:
                instance.bill.installmentPlan.totalPaid = total_paid
                instance.bill.installmentPlan.save(update_fields=['totalPaid', 'updatedAt'])
    
    #Update visit `paid`
    #Calculate current visit's paid based on today's transactions
    if instance.visit:
        instance.visit.currency = (instance.currency or None) if not instance.visit.currency else None
        instance.visit.paid = Transaction.objects.completed().filter(visit=instance.visit)\
            .exclude(Q(id__in=exclude_ids))\
            .aggregate(
                total_paid=Coalesce(Sum('amount'), Decimal('0'))
         )['total_paid']
        #save paid update
        instance.visit.save(update_fields=['paid'])
    

    #Update patient's inurance 'usedYTD' (if they have coverage)
    prev_method = getattr(instance, '_prev_method', None)
    coverage = PatientCoverage.objects.filter(patient_id=instance.patient_id).first() #getattr(instance.patient, 'patient_insurance', None)
    has_coverage = bool(coverage and (getattr(coverage, 'provider_id', False) or coverage.providerName))

    if (instance.type != 'deposit') and has_coverage:  #exclude deposits
        if instance.method == 'insurance' or prev_method == 'insurance':
            usedYTD_before = coverage.usedYTD or Decimal('0')

            #calculate total ytd used from insurance-type payments
            coverage.usedYTD = Transaction.objects.completed().filter(
                    patient=instance.patient, method='insurance', date__year=timezone.now().year)\
                .exclude(Q(id__in=exclude_ids))\
                .aggregate(
                     total_ytd=Coalesce(Sum('amount'), Decimal('0'))
                )['total_ytd']
            
            #account for refunds/deletes to change eligibility status and deductible flag
            if instance.status == 'refunded' or is_deletion:
                if (usedYTD_before > coverage.usedYTD < (coverage.annualMax or Decimal('inf')))\
                 and coverage.eligibilityStatus == 'limit_reached':
                    coverage.eligibilityStatus = coverage.determine_coverage_status(coverage.eligibilityStatus)
                    coverage.eligibilityChecked = timezone.localdate(timezone.now())
                
                if coverage.deductibleMet and coverage.coveragePercent != 100 and coverage.provider\
                 and isinstance(coverage.provider.deductible, Decimal):
                    total_paid = _calculate_patient_usedYTD(instance, exclude_ids)
                    coverage.deductibleMet = total_paid >= coverage.provider.deductible
        
        #else, check if patient has insurance and deductible amount is met
        elif (coverage.coveragePercent != 100 or not coverage.deductibleMet)\
         and coverage.provider and isinstance(coverage.provider.deductible, Decimal):
            total_paid = _calculate_patient_usedYTD(instance, exclude_ids)
            coverage.deductibleMet = total_paid >= coverage.provider.deductible
    
        #update coverage's usedYTD
        coverage.save()


def _calculate_patient_usedYTD(instance, exclude_ids=[]):
    '''Helper function to calculate and return patient's insurance usedYTD.'''
    
    return Transaction.objects.completed().filter(
                patient=instance.patient, date__year=timezone.now().year
            ).exclude(
                Q(id__in=exclude_ids) | Q(method='insurance') | Q(type='deposit')
            ).aggregate(
                total_paid=Coalesce(Sum('amount'), Decimal('0'))
            )['total_paid']


def _handle_deposit_refunds(instance):   #NOTE - awaiting decision from the frontend
    '''Helper function to handle deposit refunds.'''

    #determine if transaction is a refunded or was refunded but not any longer
    is_refunded = instance.status == 'refunded'
    was_refunded = getattr(instance, '_prev_status', None) == 'refunded'

    #Hanldle refunded deposits
    if is_refunded and not was_refunded:
        instance.bill.isCreditHeld = False
        instance.bill.description = f"{instance.bill.description}\n\n[Refunded on {timezone.localdate(timezone.now())}]"
        # instance.bill.subtotal = Decimal('0')
        # instance.bill.totalAmount = Decimal('0')
        # instance.bill.totalPaid = Decimal('0')
    
    #handle deposits previously refunded but returned to completed/correction
    elif was_refunded and not is_refunded:
        instance.bill.isCreditHeld = True
        instance.bill.description = (instance.bill.description).rsplit('[Refunded')[0].strip()
        # instance.bill.subtotal = instance.amount
        # instance.bill.totalAmount = instance.amount
        # instance.bill.totalPaid = instance.amount
    
    else:
        return instance
    
    #save changes 
    instance.bill.save(update_fields=['isCreditHeld', 'description', 'updatedAt'])



#     # #Goes with the block:
#     # if instance.bill:
#     #     #handle deposit bills separately
#     #     if instance.type == 'desposit':
#     #         instance = _handle_deposit_refunds(instance)
#     #     else:
#     #         #update bill's total paid
#     #         total_paid = Transaction.objects.completed().filter(bill=instance.bill)\
#     #             .exclude(Q(id__in=exclude_ids)
#     #             ).aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
#     #         )['total_paid']
#     #         instance.bill.totalPaid = total_paid
#     #         instance.bill.save(update_fields=['totalPaid'])
        
#     #         #update installment plan's total paid if bill has one
#     #         if instance.bill.installmentPlan:
#     #             instance.bill.installmentPlan.totalPaid = total_paid
#     #             instance.bill.installmentPlan.save(update_fields=['totalPaid', 'updatedAt'])

#     #NOTE: Scrapped for now. Awaiting decision from the frontend!
    
#     return instance
