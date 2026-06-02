from utils.base_views import *
from clinic.models import SterilizationLog
from rest_framework import status, generics
from rest_framework.response import Response
from users.utils import get_required_permission
from rest_framework.permissions import IsAuthenticated
from users.permissions import SystemUserPermissions
from rest_framework.filters import SearchFilter
from utils.filters import CustomOrderingFilter
from clinic.filters import SterilizationLogsFilter
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from clinic.serializers.sterilization_logs import (SterilizationLogSerializer, CreateSterilizationLogSerializer,
                                                   UpdateSterilizationLogSerializer, SterilizationLogsOptionsSerializer)


#STERILIZATION LOGS API VIEWS 
#List/Create sterilization logs API view
@extend_schema(tags=['Sterilization Log'])
class ListCreateSterilizationLogsAPIView(FilterListCreateAPIView):
    permission_classes = [SystemUserPermissions]
    ordering = ['-updatedAt']
    search_fields = ['operator', 'cycleType']
    ordering_fields = ['date', 'time', 'sealedAt', 'createdAt', 'updatedAt']
    filterset_class = SterilizationLogsFilter  #filters by branchId, inst_sets, date, sealedAt, & result
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('sterilization-logs', request, self)
        super().initial(request, *args, **kwargs)
    
    def get_queryset(self):
        #fetch sterilization logs queryset 
        sterilization_logs = SterilizationLog.objects.select_related('branch').all()

        if self.request.method == 'POST':
            return sterilization_logs 
        
        #filter by user
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return sterilization_logs 
        elif getattr(user, 'role', None) != 'receptionist' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            #filter queryset by branch
            return self.filter_by_branch(sterilization_logs)
        else:
            return sterilization_logs.none()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateSterilizationLogSerializer
        return SterilizationLogSerializer


#Update/delete sterilization log API view
@extend_schema(tags=['Sterilization Log'])
class UpdateDeleteSterilizationLogAPIView(UpdateAPIView, DeleteAPIView):
    queryset = SterilizationLog.objects.all()
    serializer_class = UpdateSterilizationLogSerializer
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('sterilization-logs', request, self)
        super().initial(request, *args, **kwargs)


@extend_schema(
    tags=['Sterilization Log'],
    parameters=[
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
#API view for serving choices for sterilization logs endpoints 
class RetrieveSterilizationLogsOptionsAPIView(generics.GenericAPIView):
    queryset = SterilizationLog.objects.all()
    serializer_class = SterilizationLogsOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
