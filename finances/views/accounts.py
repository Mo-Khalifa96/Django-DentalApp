from decimal import Decimal
from utils.base_views import *
from datetime import timedelta
from clinic.models import Branch
from rest_framework import status
from django.utils import timezone
from finances.utils import get_quarter
from utils.mixins import FilterByBranchMixin
from rest_framework.response import Response
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from django.db.models.functions import Coalesce
from finances.filters import PatientAccountsFilter
from patients.models import Patient, PatientCoverage
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from finances.models import Bill, Transaction, InstallmentPlan, Installment
from users.permissions import SystemUserPermissions, PatientDataPermissions
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import (F, Q, ExpressionWrapper, Count, Sum, Max, Subquery, 
                              Exists, OuterRef, IntegerField, DecimalField, DateTimeField)
from clinic.serializers.dashboard import DashboardQueryParamSerializer, ClinicRevenueSerializer
from finances.serializers.accounts import PatientAccountSerializer, ListPatientAccountsSerializer


#Helpers#
#Function to filter queryset
def get_filtered_queryset(view):
    #get current user 
    user = view.request.user

    #fetch patients queryset
    patients = Patient.objects.all()

    #filter by role
    if getattr(user, 'role', None) == 'admin':
        return patients

    elif getattr(user, 'role', None) == 'dentist':
        return patients.filter(doctor=user)

    elif getattr(user, 'role', None) == 'receptionist' or\
     view.required_permission in getattr(user, 'userPermissions', []):
        return view.filter_by_branch(patients)
    else:
        return patients.none()


#ACCOUNTS AND FINANCE VIEWS
#Retrieve patient account API view
@extend_schema(tags=['Patients'])
class RetrievePatientAccountAPIView(FilterByBranchMixin, RetrieveAPIView):
    serializer_class = PatientAccountSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'view.bills'
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_queryset(self):
        #get filtered patients queryset to lookup object
        return get_filtered_queryset(view=self)
    
    def get(self, request, *args, **kwargs):
        #Fetch current patient's id
        patient_id = self.get_object().id

        #Aggregate data
        #compute bills aggregates to determine patient's outstanding amounts
        bills_details = Bill.objects.earnings().filter(patient_id=patient_id)\
            .aggregate(
                unsettledBills_count=Count('id', filter=Q(totalPaid__isnull=True) | Q(totalPaid__lt=F('totalAmount'))),
                totalBilled=Sum('totalAmount', default=Decimal('0')),
                totalBilled_outstanding=Sum(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')),
                    default=Decimal('0')
                )
            )
        
        #compute installment plans aggregates
        installments_details = InstallmentPlan.objects.filter(treatment__patient_id=patient_id)\
            .exclude(totalPaid__gte=F('totalAmount'))\
            .annotate(
                has_active_bill=Exists(
                    Bill.objects.earnings().filter(treatment_id=OuterRef('treatment_id'))
                )
            ).aggregate(
                # pendingInstallments_count=Count('id', filter=Q(installments__paidAt__isnull=True)),
                totalInstallments_outstanding=Sum(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')),
                    default=Decimal('0')
                ),
                totalInstallment_outstanding_noBill=Sum(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')),
                    filter=Q(has_active_bill=False),
                    default=Decimal('0')
                ),
            )
        
        #compute pending installments count
        pendingInstallments_count = Installment.objects.filter(
            installmentPlan__treatment__patient_id=patient_id, paidAt__isnull=True
        ).count()
        
        #compute transaction aggregates
        transactions_details = Transaction.objects.completed().filter(patient_id=patient_id)\
            .aggregate(
                totalCollected=Sum('amount', default=Decimal('0')),
                collectedFromPatient=Sum('amount', filter=~Q(method='insurance'), default=Decimal('0')),
                collectedFromInsurer=Sum('amount', filter=Q(method='insurance'), default=Decimal('0')),
                totalCreditHeld=Sum('amount', filter=Q(type='deposit'), default=Decimal('0')),
                # currency=Max('currency', default=None)
            )
        
        #get patient coverage details
        coverage_details = PatientCoverage.objects.filter(patient_id=patient_id)\
            .annotate(yearlyBenefitRemaining=Coalesce(F('annualMax'), Decimal('0')) - Coalesce(F('usedYTD'), Decimal('0')))\
            .values('eligibilityStatus', 'effectiveTo', 'annualMax', 'usedYTD', 'yearlyBenefitRemaining')\
            .first() or {}

        #calculate total outstanding (bills outstanding + installments without a bill outstanding)
        totalOutstanding = bills_details['totalBilled_outstanding'] + installments_details['totalInstallment_outstanding_noBill']

        #Construct account dict 
        account = {
            'patientId': patient_id,
            'totalBilled': bills_details['totalBilled'],

            'totalOutstanding': totalOutstanding,
            'unsettledBillsCount': bills_details['unsettledBills_count'],
            'totalBilledOutstanding': bills_details['totalBilled_outstanding'],
            'pendingInstallmentsCount': pendingInstallments_count,
            'totalInstallmentsOutstanding': installments_details['totalInstallments_outstanding'],
            
            'totalCollected': transactions_details['totalCollected'],
            'collectedFromPatient': transactions_details['collectedFromPatient'],
            'collectedFromInsurer': transactions_details['collectedFromInsurer'],
            'totalCreditHeld': transactions_details['totalCreditHeld'],
            # 'currency': transactions_details['currency'],
            
            'insuranceCoverageStatus': coverage_details.get('eligibilityStatus'),
            'coverageEffectiveTo': coverage_details.get('effectiveTo'),
            'insuranceAnnualMax': coverage_details.get('annualMax'),
            'insuranceUsedYTD': coverage_details.get('usedYTD'),
            'yearlyBenefitRemaining': coverage_details.get('yearlyBenefitRemaining')
        }

        #Serialize data to return response
        serializer = self.get_serializer(account)

        #return response
        return Response(serializer.data, status=status.HTTP_200_OK)


#List patient accounts API view
@extend_schema(tags=['Dashboard and Analytics'])
class ListPatientAccountsAPIView(FilterListAPIView):
    serializer_class = ListPatientAccountsSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'view.bills'
    ordering = ['branch__name', 'name']  #default order of fields
    search_fields = ['name']  #search fields
    filterset_class = PatientAccountsFilter  #filters by branch/insuranceCoverageStatus/hasPendingPayments/hasPendingInstallments/hasCreditHeld
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    ordering_fields = [
        'name', 'totalBilled','totalOutstanding','unsettledBillsCount',
        'totalBilledOutstanding','pendingInstallmentsCount',
        'totalInstallmentsOutstanding','totalCollected','collectedFromPatient',
        'collectedFromInsurer','totalCreditHeld', 'insuranceCoverageStatus', 
        'insuranceUsedYTD', 'yearlyBenefitRemaining', 'lastBillUpdatedAt'
    ]


    def get_queryset(self):
        #get filtered patients queryset
        patients = get_filtered_queryset(view=self)

        #Prepare patient subqueries (for bills/installments/transactions)
        #Bills subqueries
        #bills queryset by patient
        patient_bills = Bill.objects.earnings()\
            .filter(patient_id=OuterRef('id'))\
            .order_by().values('patient_id')

        #unsettled bills count subquery
        unsettledBillsCount_subq = patient_bills.annotate(
            unsettledBills_count=Count('id', filter=Q(totalPaid__isnull=True) | Q(totalPaid__lt=F('totalAmount')))
        ).values('unsettledBills_count')

        #total billed subquery
        totalBilled_subq = patient_bills.annotate(
            totalBilled=Sum('totalAmount', default=Decimal('0'))
        ).values('totalBilled')

        #total outstanding on all of the patient's bills
        totalBilledOutstanding_subq = patient_bills.annotate(
            totalBilled_outstanding=Sum(
                ExpressionWrapper(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')), 
                    output_field=DecimalField()
                ),
                default=Decimal('0')
            )
        ).values('totalBilled_outstanding')

        #bills by updatedAt datetime
        billsUpdatedAt_subq = Bill.objects.earnings().filter(patient_id=OuterRef('id'))\
            .order_by().values('patient_id')\
            .annotate(last_updated=Max('updatedAt'))\
            .values('last_updated')

        
        #Installments subqueries
        #installment plans queryset by patient
        patient_installments = InstallmentPlan.objects.filter(
                treatment__patient_id=OuterRef('id')
            ).exclude(
                totalPaid__gte=F('totalAmount')
            ).annotate(
                has_active_bill=Exists(
                    Bill.objects.earnings().filter(treatment_id=OuterRef('treatment_id'))
                )
            ).order_by().values('treatment__patient_id')
        
        #total outstanding on all of the patient's installments
        totalInstallmentsOutstanding_subq = patient_installments.annotate(
            totalInstallments_outstanding=Sum(
                ExpressionWrapper(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')), 
                    output_field=DecimalField()
                ),
                default=Decimal('0')
            )
        ).values('totalInstallments_outstanding')

        #total outstanding on non-billed installments only
        totalInstallmentOutstanding_noBill_subq = patient_installments.annotate(
            totalInstallment_outstanding_noBill=Sum(
                ExpressionWrapper(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')), 
                    output_field=DecimalField()
                ),
                filter=Q(has_active_bill=False),
                default=Decimal('0')
            )
        ).values('totalInstallment_outstanding_noBill')

        #patient's pending installments subquery
        pendingInstallmentsCount_subq = Installment.objects.filter(
                installmentPlan__treatment__patient_id=OuterRef('id'), paidAt__isnull=True
            ).order_by().values('installmentPlan__treatment__patient_id').annotate(
                pendingInstallments_count=Count('id')
            ).values('pendingInstallments_count')
        

        #Transactions subqueries
        #transactions queryset by patient (excluding refunds)
        patient_transactions = Transaction.objects.completed()\
         .filter(patient_id=OuterRef('id')).order_by().values('patient_id')
        
        #total paid subquery
        totalCollected_subq = patient_transactions.annotate(
            total_collected=Sum('amount', default=Decimal('0'))
        ).values('total_collected')

        #total collected from patient subquery
        collectedFromPatient_subq = patient_transactions.annotate(
            total_collected_fromPatient=Sum(
                'amount', filter=~Q(method='insurance'), default=Decimal('0')
            )
        ).values('total_collected_fromPatient')
        
        #total collected from insurer subquery
        collectedFromInsurer_subq = patient_transactions.annotate(
            total_collected_fromInsurer=Sum(
                'amount', filter=Q(method='insurance'), default=Decimal('0')
            )
        ).values('total_collected_fromInsurer')

        #total deposit held subquery
        totalCreditHeld_subq = patient_transactions.annotate(
            total_deposit_held=Sum(
                'amount', filter=Q(type='deposit'), default=Decimal('0')
            )
        ).values('total_deposit_held')


        #Incorporate all subqueries into the patients queryset
        # to get the final annotated queryset
        patients_annotated_qs = patients.select_related('patient_insurance')\
            .annotate(
                totalBilled=Coalesce(Subquery(totalBilled_subq, output_field=DecimalField()), Decimal('0')),
                totalBilledOutstanding=Coalesce(Subquery(totalBilledOutstanding_subq, output_field=DecimalField()), Decimal('0')),
                unsettledBillsCount=Coalesce(Subquery(unsettledBillsCount_subq, output_field=IntegerField()), 0),
                totalInstallmentsOutstanding=Coalesce(Subquery(totalInstallmentsOutstanding_subq, output_field=DecimalField()), Decimal('0')),
                pendingInstallmentsCount=Coalesce(Subquery(pendingInstallmentsCount_subq, output_field=IntegerField()), 0),
                totalInstallmentOutstandingNoBill=Coalesce(Subquery(totalInstallmentOutstanding_noBill_subq, output_field=DecimalField()), Decimal('0')),
                totalCollected=Coalesce(Subquery(totalCollected_subq, output_field=DecimalField()), Decimal('0')),
                collectedFromPatient=Coalesce(Subquery(collectedFromPatient_subq, output_field=DecimalField()), Decimal('0')),
                collectedFromInsurer=Coalesce(Subquery(collectedFromInsurer_subq, output_field=DecimalField()), Decimal('0')),
                totalCreditHeld=Coalesce(Subquery(totalCreditHeld_subq, output_field=DecimalField()), Decimal('0')),
                lastBillUpdatedAt=Subquery(billsUpdatedAt_subq, output_field=DateTimeField())
            ).annotate(
                totalOutstanding=(F('totalBilledOutstanding') + F('totalInstallmentOutstandingNoBill')),
                insuranceCoverageStatus=F('patient_insurance__eligibilityStatus'),
                insuranceAnnualMax=F('patient_insurance__annualMax'),
                insuranceUsedYTD=F('patient_insurance__usedYTD'),
                yearlyBenefitRemaining=(
                    Coalesce(F('patient_insurance__annualMax'), Decimal('0')) 
                    - Coalesce(F('patient_insurance__usedYTD'), Decimal('0'))
                )
            )
        
        #return annotate queryset
        return patients_annotated_qs

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 20
        return super().paginate_queryset(queryset)


#Financial summary API view -- reuses `revenue` stats from /dashboard/stats/
@extend_schema(
    tags=['Dashboard and Analytics'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('dateRange', OpenApiTypes.STR, OpenApiParameter.QUERY, 
                         enum=['today', 'week', 'month', 'quarter', 'year'], required=False),
    ]
)
class FinanceSummaryAPIView(GenericAPIView):
    serializer_class = ClinicRevenueSerializer
    permission_classes = [SystemUserPermissions]
    required_permission = 'view.financialAnalytics'

    def get(self, request, *args, **kwargs):
        #Get current user 
        user = request.user 

        #Prepare filtering
        #get date today and work days window
        local_datetime = timezone.localtime(timezone.now())
        today = local_datetime.date()
        days_since_saturday = (today.weekday() + 2) % 7
        starting_saturday = today - timedelta(days=days_since_saturday)
        ending_friday = starting_saturday + timedelta(days=6)

        #serializer query parameters (if any)
        queryparam_serializer = DashboardQueryParamSerializer(data=request.query_params, context=self.get_serializer_context())
        queryparam_serializer.is_valid(raise_exception=True)
        dateRange = queryparam_serializer.validated_data.get('dateRange')
        branchId = queryparam_serializer.validated_data.get('branchId')

        #DEFINE FILTERS
        #Filter by branchId (if provided) or user's branch if non-admin
        if branchId:
            branch_filter = Q(branch_id=branchId)
        elif getattr(user, 'role', None) == 'admin'\
         or not Branch.objects.exists():
            branch_filter = Q()
        elif user.branches.count() == 1:
            branch_filter = Q(branch_id=user.branches.first().id)
        elif getattr(user, 'branch_id', None):
            branch_filter = Q(branch_id=user.branch_id)
        else:
            #fallback
            branch_ids = user.branches.values_list('id', flat=True)
            branch_filter = Q(branch_id__in=branch_ids) if branch_ids else Q(pk__in=[])
        
        #Define filters based on date range query
        if not dateRange:
            #Default filters
            createdAt_filter = Q(createdAt__month=today.month, createdAt__year=today.year)
            date_filter = Q(date__exact=today)  

        elif dateRange == 'today':
            createdAt_filter = Q(createdAt__date=today)
            date_filter = Q(date__exact=today)
        elif dateRange == 'week':
            createdAt_filter = Q(createdAt__date__range=(starting_saturday, ending_friday))
            date_filter = Q(date__range=(starting_saturday, ending_friday))
        elif dateRange == 'month':
            createdAt_filter = Q(createdAt__month=today.month, createdAt__year=today.year)
            date_filter = Q(date__month=today.month, date__year=today.year)
        elif dateRange == 'quarter':
            #determine current quarter
            quarter_range = get_quarter(today)
            createdAt_filter = Q(createdAt__date__range=quarter_range)
            date_filter = Q(date__range=quarter_range)
   
        elif dateRange == 'year':
            createdAt_filter = Q(createdAt__year=today.year)
            date_filter = Q(date__year=today.year)

        #Define revenue date filter
        revenue_date_filter = date_filter if dateRange else Q(date__month=today.month, date__year=today.year)
        

        #FINANCIAL ANALYTICS
        #Get necessary querysets for financial analytics
        #bills queryset
        bills = Bill.objects.earnings().only(   #excludes deposits/credit held
                'id', 'totalAmount', 'branch', 'createdAt'
            ).filter(branch_filter)  
        
        #get transactions queryset
        transactions = Transaction.objects.completed().only(   #excludes refunds
                'id', 'amount', 'method', 'date', 'branch'
            ).filter(branch_filter) 

        # *new*
        #account for installments without bills
        installment_plans_no_bill = InstallmentPlan.objects.filter(branch_filter).annotate(
            has_active_bill=Exists(
                Bill.objects.earnings().filter(treatment_id=OuterRef('treatment_id'))
            )
        ).filter(has_active_bill=False)
        #

        
        #Compute aggregates
        #get billing aggregates
        bills_aggregates = bills.aggregate(
            total_billed=Sum('totalAmount', default=Decimal('0')),  #used for calculating 'totalOutstanding' only
            billed_in_range=Sum('totalAmount', filter=createdAt_filter, default=Decimal('0'))   #for 'billedInPeriod'
        )

        # *new*
        #get installments aggregates
        installment_aggregates = installment_plans_no_bill.aggregate(
            installments_total=Sum('totalAmount', default=Decimal('0')),
            installments_total_in_range=Sum('totalAmount', filter=createdAt_filter, default=Decimal('0'))
        )
        #

        #get transaction aggregates
        transactions_aggregates = transactions.aggregate(
            #total paid to bills (excludes deposits -- used for calculating 'totalOutstanding' only)
            total_revenue=Sum('amount', filter=~Q(type='deposit'), default=Decimal('0')),
            revenue_in_range=Sum('amount', filter=revenue_date_filter, default=Decimal('0')),  #for 'collectedInPeriod' (includes deposits)
            total_deposit_held=Sum('amount', filter=Q(type='deposit'), default=Decimal('0')),  #total deposit `currently` held

            #aggregates for 'collectedByMethod'
            revenue_by_cash=Sum('amount', filter=Q(method='cash') & revenue_date_filter, default=Decimal('0')),
            revenue_by_card=Sum('amount', filter=Q(method='card') & revenue_date_filter, default=Decimal('0')),
            revenue_by_bank=Sum('amount', filter=Q(method='bank_transfer') & revenue_date_filter, default=Decimal('0')),
            revenue_by_insurance=Sum('amount', filter=Q(method='insurance') & revenue_date_filter, default=Decimal('0')),
            revenue_by_mobWallet=Sum('amount', filter=Q(method='mobile_wallet') & revenue_date_filter, default=Decimal('0'))
            # currency=Max('currency')
        )

        # *new*
        #calculate total outstanding from bill/installments/transaction totals
        #recalculate bills accounting for installment plans without active bills
        total_billed = bills_aggregates['total_billed'] + installment_aggregates['installments_total']
        billed_in_range = bills_aggregates['billed_in_range'] + installment_aggregates['installments_total_in_range']
        #calculate total outstanding
        totalOutstanding = total_billed - transactions_aggregates['total_revenue']
        totalOutstanding = Decimal(str(totalOutstanding)) if (totalOutstanding > 0) else Decimal('0')
        #

        #Add computed financial data 
        data = {
            'billedInPeriod': billed_in_range,    #bills_aggregates['billed_in_range'],
            'collectedInPeriod': transactions_aggregates['revenue_in_range'],
            'totalOutstanding': totalOutstanding,
            'totalCreditHeld': transactions_aggregates['total_deposit_held'],
            # 'currency': transactions_aggregates['currency']
            'collectedByMethod': {
                'cash': transactions_aggregates['revenue_by_cash'],
                'card': transactions_aggregates['revenue_by_card'],
                'bank_transfer': transactions_aggregates['revenue_by_bank'],
                'insurance': transactions_aggregates['revenue_by_insurance'],
                'mobile_wallet': transactions_aggregates['revenue_by_mobWallet'],
            }
        }


        #Serialize data to return response
        serializer = self.get_serializer(data)

        #return response
        return Response(serializer.data, status=status.HTTP_200_OK)


