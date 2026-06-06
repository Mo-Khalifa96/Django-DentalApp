from utils.base_views import *
from clinic.models import Branch
from users.permissions import AdminOnly
from finances.models import ClinicalTaxConfig
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
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
        branchId = self.request.query_params.get('branchId', None)  #TODO
        if not branchId:
            branchId = user.branch_id  #TODO
        return get_object_or_404(ClinicalTaxConfig, branch_id=branchId)
    
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


# #API view for serving branch choices -- NOTE: actually just delegate it to invoices/options/
# @extend_schema(tags=['Invoices'])
# class RetrieveClinicTaxConfigOptionsAPIView(generics.GenericAPIView):
#     queryset = ClinicalTaxConfig.objects.all()
#     serializer_class = ClinicTaxConfigOptionsSerializer
#     permission_classes = [IsAuthenticated]

#     def get(self, request, *args, **kwargs):
#         return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
