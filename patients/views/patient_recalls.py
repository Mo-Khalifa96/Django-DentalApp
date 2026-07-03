from utils.base_views import *
from users.models import User
from clinic.models import Branch
from patients.models import PatientRecall
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from users.utils import get_required_permission
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from utils.mixins import BranchToSerializerMixin
from patients.filters import PatientRecallsFilter
from users.permissions import SystemUserPermissions
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from django.db.models import Case, When, IntegerField
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.patient_recalls import (PatientRecallSerializer, CreatePatientRecallSerializer,
                                                  UpdatePatientRecallSerializer, PatientRecallsOptionsSerializer)


#PATIENT RECALLS API VIEWS 
#List/Create patient recalls API view
@extend_schema(tags=['Patient Recall'])
class ListCreatePatientRecallsAPIView(FilterListCreateAPIView):
    permission_classes = [SystemUserPermissions]
    search_fields = ['patient__name']
    ordering_fields = ['dueDate', 'status', 'contactedAt', 'createdAt', 'updatedAt']
    filterset_class = PatientRecallsFilter  #filters by branchId, dueDate, status, & type
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('patient-recalls', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #fetch patient recalls queryset
        recalls = PatientRecall.objects.select_related(
         'patient', 'branch').all().order_by('-updatedAt')
        
        if self.request.method == 'POST':
            return recalls

        #re-order queryset by status
        recalls = recalls.annotate(
            status_order=Case(
                When(status='pending', then=1),
                When(status='no_answer', then=2),
                When(status='contacted', then=3),
                When(status='confirmed', then=4),
                When(status='declined', then=5),
                output_field=IntegerField()
            )
        ).order_by('status_order')

        #filter by user 
        user = self.request.user 
        if getattr(user, 'role', None) == 'admin':
            return recalls 
        elif getattr(user, 'role', None) == 'dentist':
            return recalls.filter(patient__doctor=user)
        elif getattr(user, 'role', None) == 'receptionist' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            #filter queryset by branch 
            return self.filter_by_branch(recalls)
        else:
            return recalls.none()

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 50
        return super().paginate_queryset(queryset)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreatePatientRecallSerializer
        return PatientRecallSerializer


#Update/delete patient recall API view
@extend_schema(tags=['Patient Recall'])
class UpdateDeletePatientRecallAPIView(UpdateAPIView, DeleteAPIView):
    queryset = PatientRecall.objects.all()
    serializer_class = UpdatePatientRecallSerializer
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('patient-recalls', request, self)
        super().initial(request, *args, **kwargs)
    

#API view for serving choices for patient recall endpoints 
@extend_schema(
    tags=['Patient Recall'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('doctorId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrievePatientRecallsOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = PatientRecallsOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()  #get branchId and add doctorId
        #add doctor and branch ids to serializer context (if provided)
        doctorId = validate_uuid(self.request.query_params.get('doctorId', None), 'doctorId')
        if doctorId:
            if not User.objects.filter(id=doctorId, role__in=['dentist', 'admin']).exists():
                raise ValidationError({'doctorId': _("User not found or not registered as 'dentist'.")})
        #add doctor to serializer context   
        context['doctorId'] = doctorId
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)

