from utils.base_views import *
from patients.models import Patient, Visit
from rest_framework import status, generics
from rest_framework.response import Response
from patients.filters import PatientsFilter
from utils.mixins import BranchToFilterMixin
from users.utils import get_required_permission
from rest_framework.filters import SearchFilter
from patients.docs import get_dentalchart_schema
from users.permissions import PatientDataPermissions
from rest_framework.permissions import IsAuthenticated
from utils.filters import CustomDjangoFilterBackend, CustomOrderingFilter
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.patients import (ListPatientSerializer, RetrievePatientSerializer, 
                                           CreatePatientSerializer, UpdatePatientSerializer, 
                                           DentalChartSerializer, PatientsOptionsSerializer, 
                                           DentalChartOptionsSerializer)


#PATIENTS API VIEWS
#List/Create patients API view 
@extend_schema(tags=['Patients'])
class ListCreatePatientsAPIView(FilterListCreateAPIView, BranchToFilterMixin):
    #queryset = Patient.objects.all()
    permission_classes = [PatientDataPermissions]
    ordering = ['name']  #default order of fields
    ordering_fields = ['name', 'lastVisit', 'nextAppointment', 'createdAt']  #sorting fields
    search_fields = ['name', 'phone', 'email']  #search fields
    filterset_class = PatientsFilter  #filters by status, insurance, and branch
    filter_backends = [CustomDjangoFilterBackend, SearchFilter, CustomOrderingFilter]


    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if self.request.method == 'POST':
            return Patient.objects.prefetch_related('patient_dentalchart').all()
        
        #Fetch patients data 
        patients = Patient.objects.select_related('branch', 'doctor').all()

        #Filter queryset for list view by role
        if getattr(user, 'role', None) == 'admin':
            return patients
        
        elif getattr(user, 'role', None) == 'dentist':
            return patients.filter(doctor=user)
        
        elif getattr(user, 'role', None) == 'receptionist' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(patients)
        else:
            return patients.none()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ListPatientSerializer
        else:
            return CreatePatientSerializer



#Retrieve/update/delete patient API view
@extend_schema(tags=['Patients'])
class RetrieveUpdateDeletePatientAPIView(RetrieveUpdateDeleteAPIView):
    queryset = Patient.objects.all()
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #Determine required permission
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdatePatientSerializer
        else:
            return RetrievePatientSerializer

    def destroy(self, request, *args, **kwargs):
        patient = self.get_object()
        #soft delete patient
        Patient.objects.delete_patient(user=request.user, patient=patient)
        return Response({}, status=status.HTTP_204_NO_CONTENT)
    

#API View for serving optional choices data 
@extend_schema(
    tags=['Patients'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrievePatientsOptionsAPIView(generics.GenericAPIView):
    queryset = Visit.objects.all()
    serializer_class = PatientsOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)


######################

#Initialize schema for retrieving patient dental chart
dentalchart_view_schema = get_dentalchart_schema()


#PATIENT DENTAL CHART API VIEWS 
#Retrieve/update patient dental chart API view
@dentalchart_view_schema
class RetrieveUpdateDentalChartAPIView(RetrieveUpdateAPIView):
    queryset = Patient.objects.prefetch_related('patient_dentalchart').all()
    serializer_class = DentalChartSerializer
    permission_classes = [PatientDataPermissions]
    lookup_field = 'id'
    lookup_url_kwarg = 'id'

    def get_object(self):
        #return patient's dental chart instance
        patient = super().get_object()
        return patient.patient_dentalchart

    def initial(self, request, *args, **kwargs):
        #determine required permission 
        # self.required_permission = 'view.patientDetail' if request.method == 'GET' else 'update.patient'
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)


#API View for serving optional choices data 
@extend_schema(tags=['Dental Chart'])
class RetrieveDentalChartOptionsAPIView(generics.GenericAPIView):
    queryset = Visit.objects.all()
    serializer_class = DentalChartOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)

