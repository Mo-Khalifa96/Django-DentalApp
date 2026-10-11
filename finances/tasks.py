import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from patients.models import Visit
from clinic.models import Procedure
from django.db.models.functions import Coalesce
from finances.models import Bill, Transaction
from django.db.models import (Q, F, Func, Count, Sum, Exists, Subquery, ExpressionWrapper, 
                              OuterRef, DecimalField, BooleanField)


#Initiate logger
logger = logging.getLogger('django-q')


#Daily task to update visit expenses (for visits no with 0 cost / 0 paid)
def update_unrecorded_visit_expenses():
    ''' 
    Daily task (at 11:00 PM) to check visits with unrecorded expenses and update them 
    if a bill and a corresponding transaction was found that day.
    '''

    try:
        with transaction.atomic():
            #date today
            today = timezone.localtime(timezone.now())  #Runs 11:00 PM
            today_date = today.date()

            #First find visits with no recorded expenses
            visits = Visit.objects.select_related('patient').filter(
                date=today_date, cost__isnull=True, paid__isnull=True
             ).all()

            #Prepare subqueries
            #bills subquery
            bills_today_no_ref_subq = Bill.objects.earnings().filter(
                patient_id=OuterRef('patient_id'), createdAt__date=OuterRef('date')
             ).exclude(
                Q(visits__isnull=False) | Q(treatment__isnull=False) | Q(installmentPlan__isnull=False)
            ).values('patient_id'  #NOTE --> .values('patient_id') groups by 'patient_id' to collapse qs to one row
            ).annotate(   
                total_billed=Sum('totalAmount', default=Decimal('0'))
            )

            #transactions subquery
            transactions_today_subq = Transaction.objects.completed().filter(
                patient_id=OuterRef('patient_id'), date=OuterRef('date')
            ).values('patient_id').annotate(
                total_paid=Sum('amount', default=Decimal('0'))
            )

            #subquery to detect patients with more than one visit
            multiple_visits_subq = Visit.objects.filter(
                patient_id=OuterRef('patient_id'),
                date=OuterRef('date'),
            ).exclude(
                id=OuterRef('id'),  #exclude current visit whilst querying
            )

            #Prepare procedure-price dict for price lookup
            procedures_dict = {}
            for branch_id, procedure, price in Procedure.objects.filter(
                branch_id__in=visits.values_list('patient__branch_id', flat=True)
            ).values_list(
                'branch_id', 'name', 'price'
            ):
                procedures_dict.setdefault(branch_id, {})[procedure] = price


            #Combine subqueries
            visits = visits.annotate(
                oneVisitOnly=~Exists(multiple_visits_subq),
                hasBills=Exists(bills_today_no_ref_subq),
                totalBilled=Coalesce(
                    Subquery(
                        bills_today_no_ref_subq.values('total_billed'), 
                        output_field=DecimalField()
                    ), 
                    Decimal('0')
                ),
                hasTransactions=Exists(transactions_today_subq),
                totalPaid=Coalesce(
                    Subquery(
                        transactions_today_subq.values('total_paid'), 
                        output_field=DecimalField()
                    ), 
                    Decimal('0')
                ),
            )

            #Loop through today's visits to update them
            updated_visits = []
            for visit in visits:
                if visit.oneVisitOnly and visit.hasTransactions and visit.totalPaid > 0:
                    if visit.hasBills and (visit.totalBilled == visit.totalPaid):
                        visit.cost = visit.totalBilled
                        visit.paid = visit.totalPaid
                        updated_visits.append(visit)
                    elif visit.procedures:
                        visit.cost = sum(
                            procedures_dict
                             .get(getattr(visit.patient, 'branch_id', None), {})
                             .get(procedure, Decimal('0'))
                            for procedure in visit.procedures
                        )
                        visit.paid = visit.totalPaid
                        updated_visits.append(visit)
                    else:
                        #fallback -- just record what was paid
                        visit.cost = visit.totalPaid
                        visit.paid = visit.totalPaid
                        updated_visits.append(visit)

            #Bulk update visits
            Visit.objects.bulk_update(updated_visits, fields=['cost', 'paid'])    


    except Exception as exc:
        logger.error(f"Error updating visit expenses: {str(exc)}")
        raise  #raise the exception for Django-Q2's retry mechanism

