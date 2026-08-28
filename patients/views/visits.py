from utils.base_views import *
from django.db import transaction
from django.utils import timezone
from dateutil.relativedelta import relativedelta
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
from patients.models import Patient, Visit, PatientRecall
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
    ordering_fields = ['date', 'type']   #sort by 'date' and visit 'type' 
    filterset_class = VisitsFilter  #filter by date / search by visit 'type' and 'procedures'
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #re-order data for admins
        if getattr(request.user, 'role', None) == 'admin':
            self.ordering = ['patient__branch__name', 'patient__name', '-date', '-createdAt']
        #determine required permission
        #self.required_permission = 'view.visits' if request.method == 'GET' else 'create.visit'
        self.required_permission = get_required_permission('visits', request, self)
        super().initial(request, *args, **kwargs)

    def get_patient(self):
        patient = get_object_or_404(
            Patient.objects.select_related('doctor'),
            id=self.kwargs['id']
        )
        #check object permission and return patient object
        self.check_object_permissions(self.request, patient)
        return patient

    def get_queryset(self):
        user = self.request.user
        #Fetch patient visits for GET
        patient_visits = Visit.objects.select_related('patient', 'doctor')\
         .prefetch_related('visit_xrays').filter(patient_id=self.kwargs['id'])
        
        #filter queryset by role or permission
        if getattr(user, 'role', None) == 'dentist':
            patient = get_object_or_404(
                Patient.objects.select_related('doctor').only('id', 'doctor'),
                id=self.kwargs['id']
            )
            #check doctor's object permission and return visits
            self.check_object_permissions(self.request, patient)
            return patient_visits

            # #alternative, permission check
            # #if current doctor has at least one visit under their name or is the patient's main doctor
            # if patient_visits.filter(doctor_id=user.id).exists()\
            #  or Patient.objects.filter(doctor_id=user.id).exists():
            #     return patient_visits
            # else:
            #     return patient_visits.none()
        
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

    @transaction.atomic
    def perform_create(self, serializer):
        #Create a recall instance for 'routine_checkup' visits
        visit = serializer.save()
        patient = visit.patient

        if visit.type == Visit.VisitTypeChoices.ROUTINE_CHECKUP:
            today_date = timezone.localtime(timezone.now()).date()

            PatientRecall.objects.update_or_create(
                #look-up fields (if update)
                patient=patient, 
                type=PatientRecall.RecallTypeChoices.CHECKUP,
                status= PatientRecall.RecallStatusChoices.PENDING,

                #edit fields
                defaults={    #updateable fields
                    'branch': patient.branch,
                    'phone': patient.phone,
                    'dueDate': today_date + relativedelta(months=6),
                    'contactedAt': None,
                    'updatedAt': timezone.localtime(timezone.now()),
                }
            )


#API View for serving optional choices data 
@extend_schema(
    tags=['Visit History'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveVisitsOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = VisitOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
