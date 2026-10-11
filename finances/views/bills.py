from utils.base_views import *
from decimal import Decimal
from users.models import User
from django.http import Http404
from finances.models import Bill
from patients.models import Patient
from finances.filters import BillsFilter
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from django.db.models.functions import Coalesce
from users.utils import get_required_permission
from utils.mixins import BranchToSerializerMixin
from users.permissions import PatientDataPermissions
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import F, Q, Case, When, Value, Sum, CharField, BooleanField
from finances.serializers.bills import (BillSerializer, CreateBillSerializer,
                                        RetrieveBillSerializer, UpdateBillSerializer,
                                        AutogenerateInvoiceSerializer, BillsOptionsSerializer
                                        )


#List/Retrieve queryset annotations
annotations = {
    'status': Case(
         When(Q(totalPaid=0) | Q(totalPaid__isnull=True), then=Value('unpaid')),
         When(totalAmount__gt=F('totalPaid'), then=Value('partial')),
         When(totalAmount__lte=F('totalPaid'), then=Value('paid')),
        output_field=CharField(),
    ),
    'hasInstallmentPlan': Case(
         When(installmentPlan__isnull=False, then=Value(True)),
         When(installmentPlan__isnull=True, then=Value(False)),
        output_field=BooleanField()
    ),
    'collectedFromPatient': Coalesce(
        Sum('transactions__amount', filter=(
            Q(transactions__isDeleted=False) & 
           ~Q(transactions__status='refunded') &
           ~Q(transactions__method='insurance')
        )),
        Decimal('0')
    ),
    'collectedFromInsurer': Coalesce(
        Sum('transactions__amount', filter=(
            Q(transactions__isDeleted=False) & 
            Q(transactions__method='insurance') &
           ~Q(transactions__status='refunded')
        )),
        Decimal('0')
    ),
}

#BILLS API VIEWS 
#List/Create bills API view 
@extend_schema(tags=['Payments and Billing'])
class ListCreateBillsAPIView(FilterListCreateAPIView):
    permission_classes = [PatientDataPermissions]
    ordering = ['-updatedAt']
    ordering_fields = ['patientName', 'branchName', 'subtotal', 'totalAmount', 'totalPaid', 
                       'status', 'createdAt', 'updatedAt', 'createdBy']
    search_fields = ['description', 'patientName', 'branchName']
    filterset_class = BillsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        #add `createdBy` and `treatmentTitle` to admin's search fields
        if getattr(request.user, 'role', None) == 'admin':
            self.search_fields = ['description', 'patientName', 'branchName', 'treatmentTitle', 'createdBy']
        #determine required permission
        self.required_permission = get_required_permission('bills', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #get current user
        user = self.request.user 

        #admin gets all objects
        if getattr(user, 'role', None) == 'admin':
            return Bill.all_objects.prefetch_related('visits')\
             .select_related('patient', 'treatment', 'branch').annotate(**annotations).all()


        #fetch bills data normally for non-admins
        bills = Bill.objects.prefetch_related('visits')\
            .select_related('patient', 'treatment', 'branch').annotate(**annotations).all()

        #return on post
        if self.request.method == 'POST':
            return bills
        
        #filter queryset by role or branch
        if getattr(user, 'role', None) == 'dentist':
            return bills.filter(patient__doctor=user)
        elif self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(bills)
        else:
            return bills.none()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateBillSerializer
        return BillSerializer


#Retrieve/update/delete bill API view
@extend_schema(tags=['Payments and Billing'])
class RetrieveUpdateDeleteBillAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('bills', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #admin gets all objects
        user = self.request.user
        req_method = self.request.method
        if getattr(user, 'role', None) == 'admin':
            bills = Bill.all_objects.prefetch_related('visits')\
             .select_related('patient', 'treatment', 'branch').all()

            if req_method == 'GET':
                return bills.annotate(**annotations)  #annotate for retrieve view
            elif req_method in ('PUT', 'PATCH'):
                return bills.exclude(Q(installmentPlan__isnull=False) | Q(isDepositBill=True))  #exclude bills for installment plans and deposits
            return bills
        
        else:
            bills = Bill.objects.prefetch_related('visits')\
             .select_related('patient', 'treatment', 'branch').all()

            if req_method == 'GET':
                return bills.annotate(**annotations)
            elif req_method in ('PUT', 'PATCH'):
                return bills.exclude(Q(installmentPlan__isnull=False) | Q(isDepositBill=True))  #exclude bills for installment plans and deposits
            return bills

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateBillSerializer
        return RetrieveBillSerializer

    def destroy(self, request, *args, **kwargs):
        #get bill object
        bill = self.get_object()

        #Deposit bills shouldn't be deletable unless refunded
        if bill.isCreditHeld:
            raise ValidationError(
                {'non_field_errors': [_('Request denied. A deposit bill cannot be modified or deleted '
                                        'until the held money is refunded to the patient.')]}
            )
        
        #soft delete bill and return response
        Bill.objects.delete_bill(user=request.user, bill=bill)
        return Response({}, status=status.HTTP_204_NO_CONTENT)


#Autogenerate invoice API view
@extend_schema(tags=['Payments and Billing'])
class AutogenerateInvoiceAPIView(CreateAPIView):
    queryset = Bill.objects.all()
    required_permission = 'create.invoice'
    serializer_class = AutogenerateInvoiceSerializer
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'


#API View for serving choice options for bills
@extend_schema(
    tags=['Payments and Billing'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('patientId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('doctorId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveBillsOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = BillsOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()  #get branchId and add others
        patientId = validate_uuid(self.request.query_params.get('patientId'), 'patientId')
        doctorId = validate_uuid(self.request.query_params.get('doctorId'), 'doctorId')

        if patientId:
            try:
                Patient.objects.get(id=patientId)
            except (Patient.DoesNotExist, Http404):
                raise ValidationError({'patientId': _('Patient was not found or does not exist.')})
        
        if doctorId:
            if not User.objects.filter(id=doctorId, role__in=['dentist', 'admin']).exists():
                raise ValidationError({'doctorId': _("User not found or not registered as a doctor.")})
            
        #add patient and doctor to serializer context   
        context['doctorId'] = doctorId
        context['patientId'] = patientId
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)

