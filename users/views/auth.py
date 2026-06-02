from utils.base_views import *
from django_q.tasks import async_task
from users.docs import login_view_schema
from rest_framework import status, generics 
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated, AllowAny
from utils.swagger_utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView, TokenVerifyView, TokenBlacklistView)
from users.serializers.auth import (CustomTokenObtainPairSerializer, ChangePasswordSerializer,
                                    ResetEmailSerializer, ResetPasswordSerializer)


#Views for handling Authorization, password changes and resets 
#APIs inherited from simpleJWT 
@login_view_schema
class TokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

@extend_schema(tags=['Auth'])
class TokenRefreshView(TokenRefreshView):
    pass

@extend_schema(tags=['Auth'])
class TokenVerifyView(TokenVerifyView):
    pass

@extend_schema_view(
    post=extend_schema(
        tags=['Auth'],
        summary='Blacklist JWT Token',
        description='Blacklist refresh token (logout)'
    )
)
class TokenBlacklistView(TokenBlacklistView):
    pass


#API view for password change 
@extend_schema(tags=['Auth'])
class ChangePasswordAPIView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(instance=self.get_object(), data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'success': True, 'message': "Password changed successfully"}, status=status.HTTP_200_OK)


#API view for obtaining email for password reset 
@extend_schema(tags=['Auth'])
class ResetEmailAPIView(generics.GenericAPIView):
    serializer_class = ResetEmailSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        #get email from sent data 
        email = serializer.validated_data['email']

        #Send password reset email with Django-Q
        q_options = {'task_name': 'Password Reset Email Task', 
                     'max_attempts': 10, 'retry': 30}
        
        async_task('users.tasks.send_password_reset_email', email, 
                   q_options=q_options)
        
        return Response({'success': True, 'message': 'Email sent successfully.'}, status=status.HTTP_200_OK)


#API view for password reset from email with token
@extend_schema(tags=['Auth'])
class ResetPasswordAPIView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]

    @extend_schema(operation_id='password_reset_confirm', 
        parameters=[
            OpenApiParameter(name='uidb64', location=OpenApiParameter.PATH, type=str),
            OpenApiParameter(name='token', location=OpenApiParameter.PATH, type=str)
        ]
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        #call save method to update password
        serializer.save()

        #get name and email from serializer
        name = serializer.validated_data['name']
        email = serializer.validated_data['email']

        #send password change success email with Django-Q
        q_options = {'task_name': 'Password Reset Confirmation Email Task', 
                     'max_attempts': 5, 'retry': 30}
        async_task('users.tasks.password_reset_successful_email', name, email, q_options=q_options)
        
        return Response({'success': True, 'message': 'Password reset successfully.'}, status=status.HTTP_200_OK)
    
