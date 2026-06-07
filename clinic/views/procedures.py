from utils.base_views import *
from clinic.models import Procedure
from rest_framework import status, generics
from rest_framework.response import Response
from clinic.filters import ProceduresFilter
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from users.utils import get_required_permission
from users.permissions import SystemUserPermissions
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from clinic.serializers.procedures import (ProcedureSerializer, UpdateProcedureSerializer,
                                           ProceduresOptionsSerializer)


#PROCEDURES API VIEWS 
#List/Create procedures API view 
@extend_schema(tags=['Procedures'])
class ListCreateProceduresAPIViews(FilterListCreateAPIView):
    serializer_class = ProcedureSerializer
    permission_classes = [SystemUserPermissions]
    ordering = ['branch__name', 'name']
    search_fields = ['name', 'category']
    filterset_class = ProceduresFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('procedures', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        procedures = Procedure.objects.select_related('branch').all()

        #return full query to admin
        if getattr(user, 'role', None) == 'admin':
            return procedures
        
        #filter queryset by branch 
        return self.filter_by_branch(procedures)


#Retrieve, update, delete procedures API view 
@extend_schema(tags=['Procedures'])
class RetrieveUpdateDeleteProceduresAPIViews(RetrieveUpdateDeleteAPIView):
    queryset = Procedure.objects.all()
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('procedures', request, self)
        super().initial(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateProcedureSerializer
        return ProcedureSerializer
        

#View for retrieving procedure category choices
@extend_schema(
    tags=['Procedures'],
    parameters=[
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveProcedureOptionsAPIView(generics.GenericAPIView):
    queryset = Procedure.objects.all()
    serializer_class = ProceduresOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
