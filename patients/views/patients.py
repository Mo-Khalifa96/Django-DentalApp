from utils.base_views import *
from decimal import Decimal
from patients.models import Patient
from rest_framework import status, generics
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from patients.filters import PatientsFilter
from users.utils import get_required_permission
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from utils.mixins import BranchToSerializerMixin
from finances.models import Bill, InstallmentPlan
from users.permissions import PatientDataPermissions
from rest_framework.permissions import IsAuthenticated
from nested_multipart_parser.drf import DrfNestedParser
from django.db.models.functions import Coalesce, Greatest
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import F, Sum, Value, Exists,  ExpressionWrapper, Subquery, OuterRef, DecimalField
from patients.serializers.patients import (ListPatientSerializer, RetrievePatientSerializer, 
                                           CreatePatientSerializer, FullUpdatePatientSerializer,
                                           PartialUpdatePatientSerializer, UploadDocumentSerializer, 
                                           DeleteFileSerializer, PatientsOptionsSerializer)


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
        
        #Create a patient outstanding balance subquery 
        bills_outstanding_subquery = Bill.objects.earnings().filter(patient_id=OuterRef('id'))\
            .order_by().values('patient_id').annotate(
                total_outstanding=Sum(
                    ExpressionWrapper(
                        F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')),   #accounts for `totalPaid == None`
                        output_field=DecimalField()
                    )
                )
            ).values('total_outstanding')
        

        #Installments subquery for installment plans without an active bill
        installments_outstanding_subquery = InstallmentPlan.objects.filter(treatment__patient_id=OuterRef('id'))\
            .annotate(
                has_active_bill=Exists(
                    Bill.objects.earnings().filter(treatment_id=OuterRef('treatment_id'))
                )
            ).filter(has_active_bill=False)\
            .order_by().values('treatment__patient_id').annotate(
                total_outstanding=Sum(
                    ExpressionWrapper(F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')), output_field=DecimalField())
                )
            ).values('total_outstanding')

        #Fetch patients data
        patients = Patient.objects.select_related(
                'patient_insurance', 'branch', 'doctor'
            ).annotate(
                outstandingBalance=Greatest(
                    Coalesce(
                        Subquery(bills_outstanding_subquery, output_field=DecimalField()), 
                        Value(Decimal('0'), output_field=DecimalField())
                    ) + Coalesce(
                            Subquery(installments_outstanding_subquery, output_field=DecimalField()), 
                            Value(Decimal('0'), output_field=DecimalField())
                    ),
                    Value(Decimal('0'), output_field=DecimalField())
                )
            )

        #old pattern (bills outstanding only)
        # patients = Patient.objects.select_related(
        #         'patient_insurance', 'branch', 'doctor'
        #     ).annotate(
        #         outstandingBalance=Greatest(
        #             Coalesce(
        #                 Subquery(bills_outstanding_subquery, output_field=DecimalField()),
        #                 Value(Decimal('0'), output_field=DecimalField())
        #             ),
        #             Value(Decimal('0'), output_field=DecimalField())
        #         )
        #     )

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


#########


#OTHER
#API view for individual document uploads
@extend_schema(
    tags=['Patients'],
    responses={201: None},
    summary='Optional endpoint for document uploads',
    description=(
        'This is an optional endpoint for uploading individual documents in case you struggled with multipart requests for data + file uploads.'
        'It takes a patient ID to link each upload to its respective patient (so a patients need to be created first before document uploads).'
    )
)
class UploadDocumentAPIView(generics.GenericAPIView):
    queryset = Patient.objects.all()
    serializer_class = UploadDocumentSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'create.patient'
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        patient = get_object_or_404(Patient.objects.only('id', 'doctor'), id=self.kwargs['id'])

        #check object permission
        self.check_object_permissions(self.request, patient)

        context['patient_id'] = patient.id
        return context
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_201_CREATED)


#API view for deleting files
@extend_schema(tags=['Patients'])
class DeleteFileAPIView(DeleteAPIView):
    serializer_class = DeleteFileSerializer
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        #serialize the sent file
        serializer = DeleteFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        #delete file and return response
        serializer.delete_file()
        return Response({}, status=status.HTTP_204_NO_CONTENT)
    