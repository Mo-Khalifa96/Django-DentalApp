from utils.base_views import *
from clinic.models import Branch
from users.permissions import AdminOnly
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from utils.filters import CustomOrderingFilter
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from clinic.serializers.branches import (BranchSerializer, CreateBranchSerializer, 
                                         UpdateBranchSerializer, BranchOptionsSerializer)


#BRANCH API VIEWS 
#List/Create branches API view 
@extend_schema(tags=['Branches'])
class ListCreateBranchesAPIViews(ListCreateAPIView):
    queryset = Branch.objects.all()
    permission_classes = [AdminOnly]
    ordering = ['name']
    search_fields = ['name', 'address']
    ordering_fields = ['name', 'openTime', 'closeTime']
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return BranchSerializer
        return CreateBranchSerializer


#Retrieve/Update/Delete Branch API view
@extend_schema(tags=['Branches'])
class RetrieveUpdateDeleteBranchesAPIViews(RetrieveUpdateDeleteAPIView):
    queryset = Branch.objects.all()
    permission_classes = [AdminOnly]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateBranchSerializer
        return BranchSerializer

    def destroy(self, request, *args, **kwargs):
        #soft delete branch
        branch = self.get_object()
        Branch.objects.delete_branch(branch=branch)
        return Response({}, status=status.HTTP_204_NO_CONTENT)


#Retrieve branch options API view 
@extend_schema(
    tags=['Branches'],
    parameters=[
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveBranchOptionsAPIView(generics.GenericAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
