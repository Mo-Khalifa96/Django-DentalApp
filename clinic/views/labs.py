from utils.base_views import *
from clinic.models import Lab, LabOrder
from rest_framework import status, generics
from rest_framework.response import Response
from users.utils import get_required_permission
from rest_framework.permissions import IsAuthenticated
from users.permissions import SystemUserPermissions
from rest_framework.filters import SearchFilter
from utils.filters import CustomOrderingFilter
from utils.mixins import BranchToSerializerMixin
from clinic.filters import LabsFilter, LabOrdersFilter
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from clinic.serializers.labs import (LabSerializer, RetrieveUpdateLabSerializer, LabOrderSerializer,
                                     CreateLabOrderSerializer, UpdateLabOrderSerializer, LabOrdersOptionsSerializer)


#LABS API VIEWS 
#List/Create labs API view 
@extend_schema(tags=['Labs'])
class ListCreateLabsAPIView(FilterListCreateAPIView):
    permission_classes = [SystemUserPermissions]
    serializer_class = LabSerializer
    ordering = ['name']
    search_fields = ['name', 'address', 'contactPerson']
    filterset_class = LabsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter]

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('labs', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #fetch labs queryset 
        labs = Lab.objects.select_related('branch').all()
        
        if self.request.method == 'POST':
            return labs 
        
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return labs 
        elif getattr(user, 'role', None) == 'dentist' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            #filter queryset by branch
            return self.filter_by_branch(labs)
        else:
            return labs.none()

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 50
        return super().paginate_queryset(queryset)


#Retrieve/update/delete lab API view
@extend_schema(tags=['Labs'])
class RetrieveUpdateDeleteLabAPIView(RetrieveUpdateDeleteAPIView):
    queryset = Lab.objects.all()
    serializer_class = RetrieveUpdateLabSerializer
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('labs', request, self)
        super().initial(request, *args, **kwargs)


###################


#LAB ORDERS API VIEWS
#List/Create lab order API view
@extend_schema(tags=['Lab Orders'])
class ListCreateLabOrdersAPIView(FilterListCreateAPIView):
    permission_classes = [SystemUserPermissions]
    ordering = ['-updatedAt']
    ordering_fields = ['status', 'lab__name', 'patient__name', 'sentDate', 'dueDate', 
                       'receivedDate', 'deliveredDate', 'createdAt', 'updatedAt']
    search_fields = ['lab__name', 'procedure__name', 'patient__name', 'instructions'] 
    filterset_class = LabOrdersFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('lab-orders', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #fetch labs queryset 
        labs_orders = LabOrder.objects.select_related(
          'lab', 'patient', 'procedure', 'branch').all()
        
        if self.request.method == 'POST':
            return labs_orders 
        
        #filter by user
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return labs_orders 
        elif getattr(user, 'role', None) == 'dentist' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            #filter queryset by branch
            return self.filter_by_branch(labs_orders)
        else:
            return labs_orders.none()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateLabOrderSerializer
        return LabOrderSerializer


#Update/delete lab order API view
@extend_schema(tags=['Lab Orders'])
class UpdateDeleteLabOrderAPIView(RetrieveUpdateDeleteAPIView):
    queryset = LabOrder.objects.all()
    serializer_class = UpdateLabOrderSerializer
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('lab-orders', request, self)
        super().initial(request, *args, **kwargs)


#API View for serving choice options for lab and lab orders endpoints
@extend_schema(
    tags=['Lab Orders'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveLabOrdersOptionsAPIView(generics.GenericAPIView, BranchToSerializerMixin):
    serializer_class = LabOrdersOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
