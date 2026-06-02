from utils.base_views import *
from patients.models import Patient, TreatmentPlan
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from users.utils import get_required_permission
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from users.permissions import PatientDataPermissions
from utils.pagination import TreatmentPlansPagination
from patients.filters import TreatmentPlansFilter
from utils.filters import CustomOrderingFilter
from utils.mixins import BranchToSerializerMixin
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.treatments import (TreatmentPlanSerializer, CreateTreatmentPlanSerializer, 
                                            UpdateTreatmentPlanSerializer, TreatmentPlanOptionsSerializer)


#TREATMENT PLANS API VIEWS 
#List/Create treatment plans API view 
@extend_schema(tags=['Treatment Plans'])
class ListCreateTreatmentPlansAPIView(ListCreateAPIView):
    permission_classes = [PatientDataPermissions]
    ordering = ['-createdAt']  #default order of fields
    ordering_fields = ['status', 'createdAt']  #order by status and createdAt
    search_fields = ['title', 'items__procedure__name']  #search by title and procedure name
    filterset_class = TreatmentPlansFilter  #filters by status 
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    pagination_class = TreatmentPlansPagination
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('treatment-plans', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        try:
            patient = Patient.objects.prefetch_related('patient_treatmentplans').get(id=self.kwargs['id'])
        except Patient.DoesNotExist:
            raise NotFound('The requested patient was not found or does not exist.')
        return patient.patient_treatmentplans.prefetch_related('items', 'items__procedure').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTreatmentPlanSerializer
        else:
            return TreatmentPlanSerializer
    
    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        if self.request.method == 'POST':
            #add patient id from url to create serializer 
            serializer_context['patient_id'] = self.kwargs['id']
        return serializer_context


#Retrieve/create/update/delete patient treatment plan API view
@extend_schema(tags=['Treatment Plans'])
class RetrieveUpdateDeleteTreatmentPlanAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'treatmentId'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('treatment-plans', request, self)
        super().initial(request, *args, **kwargs)
    
    def get_object(self):
        try:
            if self.kwargs.get('id'):
                obj = TreatmentPlan.objects.prefetch_related('items').get(
                    id=self.kwargs['treatmentId'],
                    patient_id=self.kwargs['id'],
                )
            else:
                obj = TreatmentPlan.objects.prefetch_related('items').get(
                    id=self.kwargs['treatmentId']
                )
        except TreatmentPlan.DoesNotExist:
            raise NotFound('The requested treatment plan was not found or does not exist.')  
        
        #check object permission and return treatment plan
        self.check_object_permissions(self.request, obj)
        return obj

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return UpdateTreatmentPlanSerializer
        return TreatmentPlanSerializer


#API view to retrieve a single treatment plan independent of patient
@extend_schema(tags=['Treatment Plans'])
class LookupTreatmentPlanAPIView(RetrieveAPIView):
    queryset = TreatmentPlan.objects.prefetch_related('items').all()
    serializer_class = TreatmentPlanSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'view.treatments'
    lookup_url_kwarg = 'id'
    lookup_field = 'id'



#API View for serving choice options for treatment plan creation / updates
@extend_schema(
    tags=['Treatment Plans'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveTreatmentPlansOptionsAPIView(generics.GenericAPIView, BranchToSerializerMixin):
    queryset = TreatmentPlan.objects.all()
    serializer_class = TreatmentPlanOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
