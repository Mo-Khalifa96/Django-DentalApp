from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from django.dispatch import receiver
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
    if not instance._state.adding:
        try:
            instance._prev_method = Transaction.all_objects.get(id=instance.id).method
        except:
            instance._prev_method = None

#Signal for updating transaction-related data upon saving (bill/visit/installments/insurance)
@receiver([post_save, pre_delete], sender=Transaction)
def update_transaction_aggregates(sender, instance, **kwargs):
    #Determine type of signal/operation
    is_deletion = kwargs.get('signal') is pre_delete

    #Handle transaction deletion (soft-delete & hard delete)
    exclude_ids = []
    if is_deletion or instance.isDeleted:
        #remove installment's paidAt and transaction
        Installment.objects.filter(transaction_id=instance.id)\
         .update(paidAt=None, transaction=None)

        #add transaction id to exclude
        exclude_ids.append(instance.id)

    #Update bill `totalPaid`
    #Calculate current bill's totalPaid from all related transactions so far
    if instance.bill:
        #update bill's total paid
        total_paid = Transaction.objects.filter(bill=instance.bill).exclude(id__in=exclude_ids)\
            .aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
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
        instance.visit.paid = Transaction.objects.filter(visit=instance.visit).exclude(id__in=exclude_ids)\
            .aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
        )['total_paid']
        #save paid update
        instance.visit.save(update_fields=['paid'])
    

    #Update patient's inurance `usedYTD`
    prev_method = getattr(instance, '_prev_method', None)
    has_coverage = instance.patient and getattr(instance.patient, 'patient_insurance', None)
    is_insurance_transaction = (instance.method == 'insurance') or (prev_method == 'insurance')

    if has_coverage:
        if is_insurance_transaction:
            #get coverage instance
            coverage = instance.patient.patient_insurance

            #calculate total ytd used from insurance-type payments
            coverage.usedYTD = Transaction.objects.filter(
                    patient=instance.patient, method='insurance', date__year=timezone.now().year
                 ).exclude(id__in=exclude_ids)\
                  .aggregate(
                     total_ytd=Coalesce(Sum('amount'), Decimal('0'))
                )['total_ytd']
    
        #else, check if patient has insurance and deductible amount is met
        elif (coverage.coveragePercent != 100 or not coverage.deductibleMet)\
         and coverage.provider and isinstance(coverage.provider.deductible, Decimal):
            
            total_paid = Transaction.objects.filter(
                    patient=instance.patient, date__year=timezone.now().year
                ).exclude(id__in=exclude_ids, method=Transaction.PaymentMethodChoices.INSURANCE)\
                 .aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
                )['total_paid']
            
            if total_paid >= coverage.provider.deductible:
                coverage.deductibleMet = True
    
        #update coverage's usedYTD
        coverage.save()
