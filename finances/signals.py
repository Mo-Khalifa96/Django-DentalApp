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
    if action in ('post_add', 'post_remove', 'post_clear'):
        #calculate cost for each affected visit
        for visit in instance.visits.all():
            visit.cost = Bill.objects.filter(visits=visit)\
                .aggregate(totalCost=Coalesce(Sum('totalAmount'), Decimal('0')))['totalCost']
            #save cost update
            visit.save(update_fields=['cost'])

#NOTE:
#For the above signal to work, you have to trigger by 
# creating/updating manually, as in:
# def create(self, validated_data):
#     visits = validated_data.pop('visits', [])
#     bill = Bill.objects.create(**validated_data)
#     bill.visits.set(visits)   #triggers m2m_changed signal
#     return bill

# def update(self, instance, validated_data):
#     visits = validated_data.pop('visits', None)
#     instance = super().update(instance, validated_data)
#     if visits is not None:
#         instance.visits.set(visits)   #triggers m2m_changed signal
#     return instance

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

