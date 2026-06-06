from utils.base_views import *
from users.models import User
from users.filters import UsersFilter
from users.permissions import AdminOnly
from rest_framework import status, generics 
from rest_framework.response import Response
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from users.serializers.users import (CreateUserSerializer, ListUsersSerializer, RetrieveUserSerializer, 
                                     UpdateUserSerializer, UsersOptionsSerializer)


#USERS API VIEWS 
#Create new user API view
@extend_schema(tags=['Users'])
class ListCreateUserAPIView(ListCreateAPIView):
    queryset = User.objects.select_related('branch').all()
    permission_classes = [AdminOnly]
    ordering = ['name', '-createdAt']
    ordering_fields = ['name']
    search_fields = ['name', 'email']
    filterset_class = UsersFilter 
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ListUsersSerializer
        else:
            return CreateUserSerializer


#Retrieve user profile API view 
@extend_schema(tags=['Users'])
class RetrieveUserProfileAPIView(RetrieveAPIView):  #connects to /auth/me/ only
    queryset = User.objects.all()
    serializer_class = RetrieveUserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


#Retrieve/Update/Delete user API view 
@extend_schema(tags=['Users'])
class RetrieveUpdateDeleteUserAPIView(RetrieveUpdateDeleteAPIView):
    queryset = User.objects.select_related('branch').all()
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_permissions(self):
        if self.request.method == 'DELETE':
            return [AdminOnly()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateUserSerializer
        else:
            return RetrieveUserSerializer
        
    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        serializer_context['user_id'] = self.kwargs['id']
        return serializer_context

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        #soft delete user
        User.objects.delete_user(request_user=request.user, user=user)
        return Response({}, status=status.HTTP_204_NO_CONTENT)
    

#API view for serving choices data 
@extend_schema(
    tags=['Users'],
    parameters=[
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveUsersOptionsAPIView(generics.GenericAPIView):
    queryset = User.objects.all()
    serializer_class = UsersOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)

