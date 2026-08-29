from utils.base_views import *
from patients.models import Patient
from rest_framework import status, generics
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from patients.filters import PatientsFilter
from users.utils import get_required_permission
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from utils.mixins import BranchToSerializerMixin
from patients.docs import get_dentalchart_schema
from users.permissions import PatientDataPermissions
from rest_framework.permissions import IsAuthenticated
from nested_multipart_parser.drf import DrfNestedParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.patients import (ListPatientSerializer, RetrievePatientSerializer, 
                                           CreatePatientSerializer, FullUpdatePatientSerializer,
                                           PartialUpdatePatientSerializer, DentalChartSerializer, 
                                           UploadDocumentSerializer, PatientsOptionsSerializer, 
                                           DentalChartOptionsSerializer)


#PATIENTS API VIEWS
#List/Create patients API view 
@extend_schema(tags=['Patients'])
class ListCreatePatientsAPIView(FilterListCreateAPIView):
    #queryset = Patient.objects.all()
    permission_classes = [PatientDataPermissions]
    ordering = ['branch__name', 'name']  #default order of fields
    ordering_fields = ['name', 'lastVisit', 'nextAppointment', 'createdAt']  #sorting fields
    search_fields = ['name', 'phone', 'email', 'patient_insurance__providerName']  #search fields
    filterset_class = PatientsFilter  #filters by status, branch, and insurance provider
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    parser_classes = [JSONParser, DrfNestedParser, FormParser]

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)


    def get_queryset(self):
        user = self.request.user
        if self.request.method == 'POST':
            return Patient.objects.select_related('patient_dentalchart', 'patient_insurance')\
                    .prefetch_related('patient_documents').all()
        
        #Fetch patients data 
        patients = Patient.objects.select_related(
                'patient_insurance', 'branch', 'doctor'
            ).all()

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
    queryset = Patient.objects.select_related('patient_insurance', 'branch', 'doctor')\
                .prefetch_related('patient_documents').all()
    permission_classes = [PatientDataPermissions]
    parser_classes = [JSONParser, DrfNestedParser, FormParser]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #Determine required permission
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)

    def get_serializer_class(self):
        req_method = self.request.method
        if req_method == 'PUT':
            return FullUpdatePatientSerializer
        elif req_method == 'PATCH':
            return PartialUpdatePatientSerializer
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
class RetrievePatientsOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
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


#API view for serving optional choices data 
@extend_schema(tags=['Dental Chart'])
class RetrieveDentalChartOptionsAPIView(generics.GenericAPIView):
    serializer_class = DentalChartOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)


#Other
#API view for individual document uploads
@extend_schema(
    tags=['Patients'],
    responses={200: None},
    summary='Optional endpoint for document uploads.',
    description=(
        'This is an optional endpoint for uploading individual documents in case you struggled with multipart requests for data + file uploads.'
        'It takes a patient ID to link each upload to its respective patient (so a patients need to be created first before document uploads).'
    )
)
class UploadDocumentAPIView(generics.GenericAPIView):
    queryset = Patient.objects.all()
    serializer_class = UploadDocumentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        patient = get_object_or_404(Patient.objects.only('id'), id=self.kwargs['id'])
        context['patient_id'] = patient.id
        return context
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK)


