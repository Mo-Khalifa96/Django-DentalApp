from utils.base_views import *
from clinic.models import Branch
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from finances.models import InsuranceProvider
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from users.utils import get_required_permission
from utils.mixins import BranchToSerializerMixin
from users.permissions import SystemUserPermissions
from rest_framework.exceptions import ValidationError
from finances.filters import InsuranceProvidersFilter
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from finances.serializers.insurance_providers import (InsuranceProviderSerializer, 
                                                    RetrieveUpdateDeleteInsuranceProviderSerializer,
                                                    InsuranceProvidersOptionsSerializer)


#INSURANCE PROVIDERS API VIEWS
#List/Create insurance providers API view
@extend_schema(tags=['Insurance'])
class ListCreateInsuranceProvidersAPIView(FilterListCreateAPIView):
    serializer_class = InsuranceProviderSerializer
    permission_classes = [SystemUserPermissions]
    ordering = ['branch__name', 'name']
    ordering_fields = ['coveragePercent', 'annualMax', 'deductible']
    search_fields = ['name', 'fullName', 'contact', 'region', 'notes']
    filterset_class = InsuranceProvidersFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        #determin required permission
        self.required_permission = get_required_permission('insurance-providers', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #fetch insurance providers data 
        providers = InsuranceProvider.objects.select_related('branch').all()

        #return on post
        if self.request.method == 'POST':
            return providers

        #return full query to admin or on post requests
        user = self.request.user 
        if getattr(user, 'role', None) == 'admin':
            return providers 
        
        #filter queryset by branch
        return self.filter_by_branch(providers)


#Retrieve/update/delete insurance provider API view
@extend_schema(tags=['Insurance'])
class RetrieveUpdateDeleteInsuranceProviderAPIView(RetrieveUpdateDeleteAPIView):
    queryset = InsuranceProvider.objects.select_related('branch').all()
    serializer_class = RetrieveUpdateDeleteInsuranceProviderSerializer
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'providerId'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determin required permission
        self.required_permission = get_required_permission('insurance-providers', request, self)
        super().initial(request, *args, **kwargs)



#API View for serving choice options for insurance providers
@extend_schema(
    tags=['Insurance'],
    parameters=[
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveInsuranceProvidersOptionsAPIView(generics.GenericAPIView):
    serializer_class = InsuranceProvidersOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
