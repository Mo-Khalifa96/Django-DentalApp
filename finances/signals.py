from datetime import date
from decimal import Decimal
from django.db.models import Sum
from django.dispatch import receiver
from finances.models import Bill, Transaction
from django.db.models.functions import Coalesce
from django.db.models.signals import m2m_changed
from django.db.models.signals import pre_save, post_save, post_delete


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


#Signal to capture transaction method on updated instance 
@receiver(pre_save, sender=Transaction)
def track_transaction_method_changes(sender, instance, **kwargs):
    if not instance._state.adding:
        try:
            instance._prev_method = Transaction.all_objects.get(id=instance.id).method
        except:
            instance._prev_method = None

#Signal for updating transaction-related data (bill/visit/insurance)
@receiver(post_save, sender=Transaction)
def update_transaction_aggregates(sender, instance, **kwargs):

    #Update bill `totalPaid`
    #Calculate current bill's totalPaid from all related transactions so far
    if instance.bill:
        instance.bill.totalPaid = Transaction.objects.filter(bill=instance.bill)\
                .aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
            )['total_paid']
        instance.bill.save(update_fields=['totalPaid'])
    
    #Update visit `paid`
    #Calculate current visit's paid based on today's transactions
    if instance.visit:
        instance.visit.paid = Transaction.objects.filter(visit=instance.visit)\
            .aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
        )['total_paid']
        #save paid update
        instance.visit.save(update_fields=['paid'])
    
    #Update patient's inurance `usedYTD`
    prev_method = getattr(instance, '_prev_method', None)
    update_coverage = instance.method == 'insurance' or prev_method == 'insurance'

    if update_coverage and instance.patient and\
     getattr(instance.patient, 'patient_insurance', None):
        #get coverage instance 
        coverage = instance.patient.patient_insurance

        #calculate total ytd used from insurance-type payments
        coverage.usedYTD = Transaction.objects.filter(
            patient=instance.patient, method='insurance', date__year=date.today().year
                ).aggregate(total_ytd=Coalesce(Sum('amount'), Decimal('0'))
            )['total_ytd']
        
        #update coverage's usedYTD
        coverage.save(update_fields=['usedYTD'])
