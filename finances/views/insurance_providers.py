from decimal import Decimal
from utils.base_views import *
from patients.models import PatientCoverage
from rest_framework import status, generics
from rest_framework.response import Response
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from users.utils import get_required_permission
from users.permissions import SystemUserPermissions
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from django.contrib.postgres.aggregates import ArrayAgg
from finances.models import Transaction, InsuranceProvider
from django.db.models.functions import Coalesce, JSONObject
from django.contrib.postgres.expressions import ArraySubquery
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from finances.filters import InsuranceProvidersFilter, InsuranceProvidersStatsFilter
from django.db.models import (F, Q, Count, Sum, Value, Subquery, OuterRef, IntegerField, DecimalField, JSONField)
from finances.serializers.insurance_providers import (InsuranceProviderSerializer, 
                                                    RetrieveUpdateDeleteInsuranceProviderSerializer,
                                                    InsuranceProvidersStatisticsSerializer,
                                                    InsuranceProvidersOptionsSerializer)

#INSURANCE PROVIDERS API VIEWS
#List/Create insurance providers API view
@extend_schema(tags=['Insurance'])
class ListCreateInsuranceProvidersAPIView(FilterListCreateAPIView):
    serializer_class = InsuranceProviderSerializer
    permission_classes = [SystemUserPermissions]
    ordering = ['branch__name', 'name']
    ordering_fields = ['coveragePercent', 'annualMax', 'deductible']
    search_fields = ['name', 'fullName', 'contact', 'region', 'notes']
    filterset_class = InsuranceProvidersFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        #determin required permission
        self.required_permission = get_required_permission('insurance-providers', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #fetch insurance providers data 
        providers = InsuranceProvider.objects.select_related('branch').all()

        #return on post
        if self.request.method == 'POST':
            return providers

        #return full query to admin or on post requests
        user = self.request.user 
        if getattr(user, 'role', None) == 'admin':
            return providers 
        
        #filter queryset by branch
        return self.filter_by_branch(providers)


#Retrieve/update/delete insurance provider API view
@extend_schema(tags=['Insurance'])
class RetrieveUpdateDeleteInsuranceProviderAPIView(RetrieveUpdateDeleteAPIView):
    queryset = InsuranceProvider.objects.select_related('branch').all()
    serializer_class = RetrieveUpdateDeleteInsuranceProviderSerializer
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'providerId'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determin required permission
        self.required_permission = get_required_permission('insurance-providers', request, self)
        super().initial(request, *args, **kwargs)



#Insurance providers stats API view
@extend_schema(tags=['Dashboard and Analytics'])
class ListInsuranceProvidersStatisticsAPIView(FilterListAPIView):
    serializer_class = InsuranceProvidersStatisticsSerializer
    permission_classes = [SystemUserPermissions]
    required_permission = 'view.insuranceProviders'
    ordering = ['branch__name', 'name']
    search_fields = ['name']
    filterset_class = InsuranceProvidersStatsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    ordering_fields = [
        'name', 'coveragePercent', 'annualMax', 'coveredPatientsCount', 
        'patientsTotalAnnualMax', 'patientsTotalUsedYTD', 'totalYearlyBenefitRemaining', 
        'totalCollected', 'relatedBillsCount'
    ]


    def get_queryset(self):
        #fetch insurance providers data 
        providers = InsuranceProvider.objects.all()

        #filter qs by user role
        user = self.request.user 
        if getattr(user, 'role', None) != 'admin':
            providers = self.filter_by_branch(providers)


        #Prepare provider subqueries
        #patient coverages subqueries
        #get insurer-related coverages
        patient_coverages = PatientCoverage.objects.filter(provider_id=OuterRef('id'))\
            .exclude(eligibilityStatus__in=['expired', 'none']).order_by().values('provider_id')

        #number of patients under provider's care subquery
        coveredPatientsCount_subq = patient_coverages.annotate(
            coveredPatients_count=Count('id')
        ).values('coveredPatients_count')

        #total annualMax across all coverages
        patientsTotalAnnualMax_subq = patient_coverages.annotate(
            patients_total_annualMax=Sum('annualMax', filter=Q(annualMax__isnull=False), default=Decimal('0'))
        ).values('patients_total_annualMax')

        #total usedYTD this year across all coverages
        patientsTotalUsedYTD = patient_coverages.annotate(
            patients_total_usedYTD=Sum('usedYTD', filter=Q(usedYTD__isnull=False), default=Decimal('0'))
        ).values('patients_total_usedYTD')


        #insurance transaction subqueries
        #get insurer-related transactions
        insurance_transactions = Transaction.objects.completed()\
            .filter(
                patient__patient_insurance__provider_id=OuterRef('id'), method='insurance'
            )
        
        #total collected from insurer
        totalCollected_subq = insurance_transactions.values('patient__patient_insurance__provider_id')\
            .annotate(
                total_collected=Sum('amount', default=Decimal('0'))
           ).values('total_collected')

        #insurance bills subqueries
        relatedBillsCount_subq = insurance_transactions.values('patient__patient_insurance__provider_id')\
            .annotate(
                related_bills_count=Count('bill_id', filter=Q(bill__isnull=False), distinct=True)
           ).values('related_bills_count')

        
        #get related payment details (as json object)
        relatedPayments_arraySubq = insurance_transactions\
            .filter(bill__isnull=False)\
            .values('bill_id')\
            .annotate(transactionsCount=Count('id'), transactionIds=ArrayAgg('id', ordering=('-date', '-updatedAt')))\
            .annotate(payment=JSONObject(billId=F('bill_id'), transactionsCount=F('transactionsCount'), transactionIds=F('transactionIds')))\
            .values('payment')
        

        #Incorporate all subqueries into the insurance providers queryset
        # to get the final annotated queryset
        providers_annotated_qs = providers.annotate(
                coveredPatientsCount=Coalesce(
                    Subquery(coveredPatientsCount_subq, output_field=IntegerField()), 0
                ),
                patientsTotalAnnualMax=Coalesce(
                    Subquery(patientsTotalAnnualMax_subq , output_field=DecimalField()), Decimal('0')
                ),
                patientsTotalUsedYTD=Coalesce(
                    Subquery(patientsTotalUsedYTD , output_field=DecimalField()), Decimal('0')
                ),
                totalCollected=Coalesce(
                    Subquery(totalCollected_subq , output_field=DecimalField()), Decimal('0')
                ),
                relatedBillsCount=Coalesce(
                    Subquery(relatedBillsCount_subq , output_field=IntegerField()), 0
                ),
                relatedPayments=Coalesce(
                    ArraySubquery(relatedPayments_arraySubq, 
                                  output_field=ArrayField(JSONField())
                    ),
                    Value([], output_field=ArrayField(JSONField())))

            ).annotate(
                totalYearlyBenefitRemaining=(
                    Coalesce(F('patientsTotalAnnualMax'), Decimal('0')) 
                    - Coalesce(F('patientsTotalUsedYTD'), Decimal('0'))
                )
            )
        
        #return annotated queryset 
        return providers_annotated_qs

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 5
        return super().paginate_queryset(queryset)


#API View for serving choice options for insurance providers
@extend_schema(
    tags=['Insurance'],
    parameters=[
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveInsuranceProvidersOptionsAPIView(generics.GenericAPIView):
    serializer_class = InsuranceProvidersOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
