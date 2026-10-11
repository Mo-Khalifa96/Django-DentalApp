from utils.base_views import * 
from decimal import Decimal
from users.models import User
from django.http import Http404
from clinic.models import Branch
from django.utils import timezone
from django.db.models import Q, Sum, Count
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models.functions import Coalesce
from patients.filters import PatientCoverageFilter
from rest_framework.filters import SearchFilter
from utils.filters import CustomOrderingFilter
from utils.mixins import BranchToSerializerMixin
from patients.models import Patient, PatientCoverage
from users.permissions import PatientDataPermissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.patient_insurance import (ListPatientCoverageSerializer, CreatePatientCoverageSerializer,
                                                    RetrieveUpdatePatientCoverageSerializer, PatientCoverageStatisticsSerializer,
                                                    PatientCoverageOptionsSerializer)


#PATIENT COVERAGE API VIEWS
#List patient coverage plans API view
@extend_schema(tags=['Insurance'])
class ListPatientCoveragePlansAPIView(FilterListAPIView):
    serializer_class = ListPatientCoverageSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'view.patientInsurance'
    ordering = ['eligibilityStatus', 'patient__branch__name', 'patient__name']
    ordering_fields = ['eligibilityStatus', 'providerName', 'annualMax', 'usedYTD', 
                       'deductibleMet', 'eligibilityChecked', 'updatedAt']
    search_fields = ['patient__name', 'providerName', 'memberId']
    filterset_class = PatientCoverageFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def get_queryset(self):
        #fetch patient coverage plans
        coverages = PatientCoverage.objects.select_related('patient', 'provider').all()

        #filter queryset by role and/or branch
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return coverages
        
        elif getattr(user, 'role', None) == 'dentist':
            return coverages.filter(patient__doctor=user)
        
        elif self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(coverages, branch_field='patient__branch_id')
        
        else:
            return coverages.none()

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 40
        return super().paginate_queryset(queryset)


#Create/Retrieve/Update patient insurance API view
@extend_schema(tags=['Insurance'])
class CreateRetrieveUpdatePatientCoverageAPIView(CreateAPIView, RetrieveUpdateAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'patientId'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = 'view.patientInsurance' if request.method == 'GET' else 'update.patientInsurance'
        super().initial(request, *args, **kwargs)
    
    def get_object(self):
        if not hasattr(self, '_coverage_object'):
            patient = get_object_or_404(Patient.objects.only('id'), id=self.kwargs['patientId'])
            coverage = PatientCoverage.objects.select_related('patient', 'provider').get(patient_id=patient.id)
            
            #check object permission and cache coverage instance
            self.check_object_permissions(self.request, coverage)
            self._coverage_object = coverage
            return self._coverage_object

        return self._coverage_object

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreatePatientCoverageSerializer
        return RetrieveUpdatePatientCoverageSerializer
    
    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        if self.request.method != 'GET':
            #add current object to serializer context
            serializer_context['coverage'] = self.get_object()  #acts on POST too to check object permission!
        return serializer_context


@extend_schema(
    tags=['Dashboard and Analytics'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
    ]
)
class PatientCoverageStatisticsAPIView(GenericAPIView):
    serializer_class = PatientCoverageStatisticsSerializer
    permission_classes = [PatientDataPermissions] 
    required_permission = 'view.patientInsurance'

    def get(self, request, *args, **kwargs):
        #Prepare filtering by role/branch/year
        #get current user
        user = request.user
        
        #fetch branch id from url
        branchId = validate_uuid(self.request.query_params.get('branchId'), 'branchId')

        #validate branch and determine branch filter
        if branchId:
            try:
                Branch.objects.get(id=branchId)
            except (Branch.DoesNotExist, Http404):
                raise ValidationError({'branchId': _('Branch was not found or does not exist.')})
            
            #assign branch filter 
            branch_filter = Q(patient__branch_id=branchId)
        
        #if it has no branches, return empty filter
        elif getattr(user, 'role', None) == 'admin'\
         or not Branch.objects.exists():
            branch_filter = Q()
        
        #otherwise determine filtering using user's branch/branches
        elif user.branches.count() == 1: #if user is associated with only one branch, use it
            branch_filter = Q(patient__branch_id=user.branches.first().id)
            
        elif getattr(user, 'branch_id', None):   #if user has an 'active branch', use that

            branch_filter = Q(patient__branch_id=user.branch_id)
        
        else:  #fall back, use all of the user's active branches
            branch_ids = user.branches.values_list('id', flat=True)
            branch_filter = Q(patient__branch_id__in=branch_ids) if branch_ids else Q(pk__in=[])
        
        
        #Compute required aggregates
        coverage_aggregates = PatientCoverage.objects.filter(branch_filter)\
            .aggregate(
                insuredPatients=Count('patient_id', filter=Q(provider__isnull=False)),
                annualMaxTotal=Coalesce(Sum('annualMax', filter=Q(provider__isnull=False)), Decimal('0')),
                usedYTDTotal=Coalesce(Sum('usedYTD', filter=Q(provider__isnull=False)), Decimal('0')),
                eligibility_active=Count('id', filter=Q(eligibilityStatus='active', provider__isnull=False)),
                eligibility_expiring=Count('id', filter=Q(eligibilityStatus='expiring', provider__isnull=False)),
                eligibility_expired=Count('id', filter=Q(eligibilityStatus='expired', provider__isnull=False)),
                eligibility_maxed=Count('id', filter=Q(eligibilityStatus='limit_reached', provider__isnull=False)),
                eligibility_none=Count('id', filter=Q(eligibilityStatus='none')),
            )

        #compute total remaining and utilisation percent from aggregates
        annual_max_total = coverage_aggregates['annualMaxTotal']
        usedYTD_total = coverage_aggregates['usedYTDTotal']
        remaining_total = annual_max_total - usedYTD_total
        remaining_total = Decimal(str(remaining_total)) if (remaining_total > 0) else Decimal('0')
        utilisation_percent = round(usedYTD_total * 100 / annual_max_total) if annual_max_total > 0 else 0

        #prepare response dict
        data = {
            'insuredPatients': coverage_aggregates['insuredPatients'],
            'byEligibility': { 
                'active': coverage_aggregates['eligibility_active'],
                'expiring':coverage_aggregates['eligibility_expiring'],
                'expired': coverage_aggregates['eligibility_expired'],
                'limit_reached': coverage_aggregates['eligibility_maxed'],   #*new* -- requires documentation
                'none': coverage_aggregates['eligibility_none'],
            },
            'annualMaxTotal': annual_max_total,
            'usedYTDTotal': usedYTD_total,
            'remainingTotal': remaining_total,
            'utilisationPercent': utilisation_percent
        }

        #serialize data and return response
        serializer = self.get_serializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


#API View for serving choice options for lab and lab orders endpoints
@extend_schema(
    tags=['Insurance'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('doctorId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrievePatientCoverageOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = PatientCoverageOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()  #get branchId and add doctorId
        doctorId = validate_uuid(self.request.query_params.get('doctorId'), 'doctorId')

        if doctorId:
            if not User.objects.filter(id=doctorId, role__in=['dentist', 'admin']).exists():
                raise ValidationError({'doctorId': _("User not found or not registered as a doctor.")})
            
        #add doctor to serializer context
        context['doctorId'] = doctorId
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
