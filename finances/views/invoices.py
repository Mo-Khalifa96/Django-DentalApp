from utils.base_views import *
from users.models import User
from django.db.models import Q
from finances.models import Invoice
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from finances.filters import InvoicesFilter
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
from finances.serializers.invoices import (InvoiceSerializer, RetrieveInvoiceSerializer, 
                                           CreateInvoiceSerializer, UpdateInvoiceSerializer, 
                                           UpdateInvoiceStatusSerializer, InvoicesOptionsSerializer)


#INVOICES API VIEWS 
#List/Create invoices API view
@extend_schema(tags=['Invoices'])
class ListCreateInvoicesAPIView(FilterListCreateAPIView):
    permission_classes = [PatientDataPermissions]
    ordering = ['branch__name', '-issuedAt', '-submittedAt', 'patient__name']
    ordering_fields = ['patientName', 'branchName', 'total', 'subtotal', 
                       'issuedAt', 'submittedAt', 'createdBy', 'createdAt']
    search_fields = ['patientName', 'branchName', 'invoice_items__description']
    filterset_class = InvoicesFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        #add `createdBy` and `billDescription` to admin's search fields
        if getattr(request.user, 'role', None) == 'admin':
            self.search_fields = ['patientName', 'branchName', 'billDescription', 'invoice_items__description', 'createdBy']
        #determine required permission
        self.required_permission = get_required_permission('invoices', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #get current user 
        user = self.request.user 

        #admin gets all objects
        if getattr(user, 'role', None) == 'admin':
            return Invoice.all_objects.prefetch_related('invoice_items')\
                .select_related('bill', 'patient', 'branch').all()

        #fetch invoices data normally for non-admins
        invoices = Invoice.objects.prefetch_related('invoice_items')\
                .select_related('bill', 'patient', 'branch').all()
        
        #return on post
        if self.request.method == 'POST':
            return invoices
        
        #filter queryset by role or branch
        if getattr(user, 'role', None) == 'dentist':
            return invoices.filter(Q(patient__doctor=user) | Q(createdBy=user.name))
        elif self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(invoices)
        else:
            return invoices.none()

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 25
        return super().paginate_queryset(queryset)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateInvoiceSerializer
        return InvoiceSerializer


#Retrieve/update/delete invoice API view
@extend_schema(tags=['Invoices'])
class RetrieveUpdateDeleteInvoiceAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('invoices', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #admin gets all objects
        user = self.request.user 
        if getattr(user, 'role', None) == 'admin':
            return Invoice.all_objects.prefetch_related('invoice_items')\
                .select_related('bill', 'patient', 'branch').all()
        else:
            return Invoice.objects.prefetch_related('invoice_items')\
                .select_related('bill', 'patient', 'branch').all()
    
    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return UpdateInvoiceSerializer
        elif self.request.method == 'PATCH':
            return UpdateInvoiceStatusSerializer
        return RetrieveInvoiceSerializer

    def destroy(self, request, *args, **kwargs):
        invoice = self.get_object()
        #soft delete invoice and return response
        Invoice.objects.delete_invoice(user=request.user, invoice=invoice)
        return Response({}, status=status.HTTP_204_NO_CONTENT)


#API view for serving choice options for invoices
@extend_schema(
    tags=['Invoices'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('doctorId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveInvoicesOptionsAPIView(generics.GenericAPIView, BranchToSerializerMixin):
    serializer_class = InvoicesOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()  #get branchId and add doctorId
        doctorId = validate_uuid(self.request.query_params.get('doctorId'))

        if doctorId:
            if not User.objects.filter(id=doctorId, role__in=['dentist', 'admin']).exists():
                raise ValidationError({'doctorId': _("User not found or not registered as a doctor.")})
            
        #add doctor to serializer context
        context['doctorId'] = doctorId
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
