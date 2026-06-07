from utils.base_views import *
from patients.models import Patient, Visit
from rest_framework import status, generics
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from users.utils import get_required_permission
from utils.filters import CustomOrderingFilter
from patients.filters import VisitsFilter
from rest_framework.filters import SearchFilter
from utils.mixins import BranchToSerializerMixin
from users.permissions import PatientDataPermissions
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.visits import PatientVisitSerializer, VisitOptionsSerializer



#PATIENT VISITS API VIEWS 
#List/Create patient visits API view 
@extend_schema(tags=['Visit History'])
class ListCreateVisitsAPIView(ListCreateAPIView):
    serializer_class = PatientVisitSerializer
    permission_classes = [PatientDataPermissions]
    ordering = ['-date', '-createdAt']  #default order fields 
    ordering_fields = ['date', 'type']   #sort by date and visit type 
    search_fields = ['type']  #search by visit type
    filterset_class = VisitsFilter  #filter by date / search by procedure names
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #re-order data for admins
        if getattr(request.user, 'role', None) == 'admin':
            self.ordering = ['branch__name', 'patient__name', '-date', '-createdAt']

        #determine required permission
        #self.required_permission = 'view.visits' if request.method == 'GET' else 'create.visit'
        self.required_permission = get_required_permission('visits', request, self)
        super().initial(request, *args, **kwargs)

    def get_patient(self):
        patient = get_object_or_404(
            Patient.objects.prefetch_related('patient_xrays'),
            id=self.kwargs['id']
        )
        #check object permission and return patient object
        self.check_object_permissions(self.request, patient)
        return patient

    def get_queryset(self):
        user = self.request.user
        #Fetch patient visits for GET
        patient_visits = Visit.objects.select_related('patient', 'doctor')\
         .prefetch_related('patient__patient_xrays').filter(patient_id=self.kwargs['id'])
        
        if getattr(user, 'role', None) == 'dentist':
            return patient_visits.filter(doctor=user)

        elif getattr(user, 'role', None) == 'admin' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            return patient_visits

        else:
            return patient_visits.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method == 'POST':
            context['patient'] = self.get_patient()
        return context

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 10
        return super().paginate_queryset(queryset)


#API View for serving optional choices data 
@extend_schema(
    tags=['Visit History'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveVisitsOptionsAPIView(generics.GenericAPIView, BranchToSerializerMixin):
    queryset = Visit.objects.all()
    serializer_class = VisitOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
