from utils.base_views import *
from clinic.models import Branch
from users.permissions import AdminOnly
from django.http.response import Http404
from utils.validators import validate_uuid
from finances.models import ClinicalTaxConfig
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound, ValidationError
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from finances.serializers.tax_config import (TaxConfigSerializer, CreateTaxConfigSerializer)


#CLINIC TAX CONFIGURATION API VIEWS
#Create/Retrieve/Update clinic tax configuration API view
@extend_schema(
    tags=['Invoices'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
    ]
)
class ClinicTaxConfigAPIView(CreateAPIView, RetrieveUpdateAPIView):
    queryset = ClinicalTaxConfig.objects.select_related('branch').all()
    permission_classes = [AdminOnly]

    def get_object(self):
        user = self.request.user
        branchId = validate_uuid(self.request.query_params.get('branchId'), 'branchId')
        if not branchId:
            if user.branches.count() == 1:
                branchId = user.branches.first().id
            else:
                branchId = getattr(user, 'branch_id', None)

        #handle one-to-one relation to tax config or clinic without branches
        branch_filter = {'branch_id': branchId} if branchId else {'branch': None}

        try:
            obj = get_object_or_404(ClinicalTaxConfig, **branch_filter)
        except (ClinicalTaxConfig.DoesNotExist, Http404):
            raise NotFound(_('The requested tax configuration was not found or does not exist.'))
        except ClinicalTaxConfig.MultipleObjectsReturned:
            raise ValidationError(_('Clinic branch must be provided to determine the associated tax configuration.'))
        return obj
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTaxConfigSerializer
        return TaxConfigSerializer
    
    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        if self.request.method == 'POST':
            branchId = self.request.query_params.get('branchId')
            if branchId:
                #verify branch exists then filter by branch
                branch = get_object_or_404(Branch.objects.only('id'), id=branchId)
                #add branch id from url to create serializer
                serializer_context['branch'] = branch
        return serializer_context

