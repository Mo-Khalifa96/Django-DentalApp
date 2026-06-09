from decimal import Decimal
from django.db.models import Sum
from django.dispatch import receiver
from finances.models import Bill, Transaction
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.db.models.signals import m2m_changed


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


#Signal for updating visit's paid amount after a transaction
@receiver(post_save, sender=Transaction)
def update_visit_paid(sender, instance, **kwargs):
    #Calculate current bill's totalPaid from all related transactions so far
    if instance.bill:
        totalPaid = Transaction.objects.filter(bill=instance.bill)\
                .aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
            )['total_paid']
        instance.bill.totalPaid = totalPaid
        instance.bill.save(update_fields=['totalPaid'])

    #Calculate current visit's paid based on today's transactions
    if instance.visit:
        instance.visit.paid = Transaction.objects.filter(visit=instance.visit)\
            .aggregate(total_paid=Coalesce(Sum('amount'), Decimal('0'))
        )['total_paid']
        #save paid update
        instance.visit.save(update_fields=['paid'])

