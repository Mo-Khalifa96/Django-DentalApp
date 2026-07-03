from utils.base_views import * 
from users.models import User
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
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
                                                    RetrieveUpdatePatientCoverageSerializer, PatientCoverageOptionsSerializer)


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
