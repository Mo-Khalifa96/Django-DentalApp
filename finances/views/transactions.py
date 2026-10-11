from utils.base_views import *
from users.models import User
from django.db.models import Q 
from django.http import Http404
from django.db import transaction
from patients.models import Patient
from finances.models import Transaction
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from finances.filters import TransactionsFilter
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from users.utils import get_required_permission
from utils.mixins import BranchToSerializerMixin
from users.permissions import PatientDataPermissions
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from finances.serializers.transactions import (TransactionSerializer, RetrieveTransactionSerializer, 
                                        CreateTransactionSerializer, UpdateTransactionSerializer, 
                                        CreateDepositTransactionSerializer, RefundTransactionSerializer, 
                                        RequestCorrectionSerializer, TransactionsOptionsSerializer)


#TRANSACTIONS API VIEWS
#List/Create transactions API view
@extend_schema(tags=['Payments and Billing'])
class ListCreateTransactionsAPIView(FilterListCreateAPIView):
    permission_classes = [PatientDataPermissions]
    ordering = ['branch__name', '-date', 'patientName']
    ordering_fields = ['patientName', 'branchName', 'date', 'amount', 'type', 'status', 'createdBy']
    search_fields = ['patientName', 'branchName', 'notes']
    filterset_class = TransactionsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        #add `createdBy` and `billDescription` to admin's search fields
        if getattr(request.user, 'role', None) == 'admin':
            self.search_fields = ['patientName', 'branchName', 'billDescription', 'notes', 'createdBy']
        #determine required permission
        self.required_permission = get_required_permission('transactions', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #get current user
        user = self.request.user

        #admin gets all objects
        if getattr(user, 'role', None) == 'admin':
            return Transaction.all_objects.select_related(
                'bill', 'bill__installmentPlan', 'patient', 'visit', 'branch'
            ).all()
        
        #fetch transactions data normally for non-admins
        transactions = Transaction.objects.select_related(
            'bill', 'bill__installmentPlan', 'patient', 'visit', 'branch'
        ).all()

        #return on post
        if self.request.method == 'POST':
            return transactions
        
        #filter queryset by role or branch
        if getattr(user, 'role', None) == 'dentist':
            return transactions.filter(patient__doctor=user)
        elif self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(transactions)
        else:
            return transactions.none()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTransactionSerializer
        return TransactionSerializer


#Update/delete transaction API view
@extend_schema(tags=['Payments and Billing'])
class RetrieveUpdateDeleteTransactionAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('transactions', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #admin gets all objects
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            transactions = Transaction.all_objects.select_related(
                    'bill', 'bill__installmentPlan', 'patient', 'visit', 'branch'
                ).all()
        else:
            transactions = Transaction.objects.select_related(
                    'bill', 'bill__installmentPlan', 'patient', 'visit', 'branch'
                ).all()
        
        #exclude transactions associated with installments for updates
        if self.request.method == 'PATCH':
            return transactions.exclude(Q(installments__isnull=False) | Q(type='installment'))
        return transactions

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return UpdateTransactionSerializer
        return RetrieveTransactionSerializer

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        #get bill object
        transaction = self.get_object()

        #soft delete bill and return response
        Transaction.objects.delete_transaction(user=request.user, transaction=transaction)
        return Response({}, status=status.HTTP_204_NO_CONTENT)


#Create deposit transaction API view
@extend_schema(tags=['Payments and Billing'])
class CreateDepositTransactionAPIView(CreateAPIView):
    queryset = Transaction.objects.select_related('patient', 'branch').all()
    serializer_class = CreateDepositTransactionSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'create.transaction'


#Refund transaction API view
@extend_schema(tags=['Payments and Billing'])
class RefundTransactionAPIView(UpdateAPIView):
    serializer_class = RefundTransactionSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'create.transaction'
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_queryset(self):
        #admin gets all objects
        user = self.request.user 
        if getattr(user, 'role', None) == 'admin':
            return Transaction.all_objects.select_related('bill', 'patient').all()
        else:
            return Transaction.objects.select_related('bill', 'patient').all()


#Request correction to a transaction API view
@extend_schema(tags=['Payments and Billing'])
class RequestCorrectionAPIView(UpdateAPIView):
    serializer_class = RequestCorrectionSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'create.transaction'
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_queryset(self):
        #admin gets all objects
        user = self.request.user 
        if getattr(user, 'role', None) == 'admin':
            return Transaction.all_objects.select_related('bill', 'patient').all()
        else:
            return Transaction.objects.select_related('bill', 'patient').all()


#API View for serving choice options for transactions
@extend_schema(
    tags=['Payments and Billing'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('patientId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('doctorId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveTransactionsOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = TransactionsOptionsSerializer
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
