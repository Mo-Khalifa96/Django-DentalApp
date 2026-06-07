from utils.base_views import *
from clinic.models import Inventory
from rest_framework import status, generics
from rest_framework.response import Response
from clinic.filters import InventoryFilter
from rest_framework.filters import SearchFilter
from users.utils import get_required_permission
from users.permissions import SystemUserPermissions
from rest_framework.permissions import IsAuthenticated
from utils.mixins import BranchToFilterMixin, BranchToSerializerMixin
from utils.filters import CustomDjangoFilterBackend, CustomOrderingFilter
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from clinic.serializers.inventory import (InventorySerializer, CreateInventoryItemSerializer,
                                        UpdateInventorySerializer, InventoryOptionsSerializer)


#INVENTORY API VIEWS 
#List/Create inventory API view 
@extend_schema(tags=['Inventory'])
class ListCreateInventoryAPIViews(FilterListCreateAPIView, BranchToFilterMixin):
    permission_classes = [SystemUserPermissions]
    ordering = ['branch__name', 'name']
    search_fields = ['name', 'category', 'unit']
    filterset_class = InventoryFilter
    filter_backends = [CustomDjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('inventory', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        inventory = Inventory.objects.select_related('branch').all()
        
        #return full query to admin
        if getattr(user, 'role', None) == 'admin':
            return inventory
        
        #filter queryset by branch 
        return self.filter_by_branch(inventory)
        
        
    def paginate_queryset(self, queryset):
        #use number of objects per page
        self.paginator.page_size = 50
        return super().paginate_queryset(queryset)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateInventoryItemSerializer
        return InventorySerializer



#Retrieve, update, delete inventory API view 
@extend_schema(tags=['Inventory'])
class RetrieveUpdateDeleteInventoryAPIViews(RetrieveUpdateDeleteAPIView):
    queryset = Inventory.objects.all()
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('inventory', request, self)
        super().initial(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateInventorySerializer
        return InventorySerializer



#View for retrieving inventory category choices for filtering
@extend_schema(
    tags=['Inventory'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveInventoryOptionsAPIView(generics.GenericAPIView, BranchToSerializerMixin):
    queryset = Inventory.objects.all()
    serializer_class = InventoryOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
