from users.models import User
from django.db import transaction
from rest_framework import serializers
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


#AUTH SERIALIZERS
#Serializer for the obtain token pair view
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        data = super().validate(attrs)
        #Add user data to response
        data['user'] = {
            'id': str(self.user.id),
            'email': self.user.email,
            'name': self.user.name,
            'role': self.user.role,
            'specialization': self.user.specialization,
            'branchId': getattr(self.user.branch, 'id', None)
        }
        return data


#Serializers for handling password changes and resets 
#Custom serializer for password change 
class ChangePasswordSerializer(serializers.ModelSerializer):
    currentPassword = serializers.CharField(write_only=True)
    newPassword = serializers.CharField(write_only=True)
    newPassword2 = serializers.CharField(write_only=True)

    class Meta:
        model = User 
        fields = ['currentPassword', 'newPassword', 'newPassword2']

    #Validate passwords
    def validate(self, data):
        #obtain passwords passed (if any)
        currentPassword = data.get('currentPassword', None)
        newPassword = data.get('newPassword', None)
        newPassword2 = data.get('newPassword2', None)

        if not currentPassword:
            raise serializers.ValidationError({'currentPassword': _('Current password is required.')})
        elif not self.instance.check_password(currentPassword):
            raise serializers.ValidationError({'currentPassword': _('Current password is incorrect.')})
        if not newPassword:
            raise serializers.ValidationError({'newPassword': _('New password is required.')})
        elif currentPassword == newPassword:
                raise serializers.ValidationError({'newPassword': _('New password must be different from the old one.')})
        if not newPassword2:
            raise serializers.ValidationError({'newPassword2': _('Password confirmation is required.')})
        elif newPassword != newPassword2:
                raise serializers.ValidationError({'newPassword2': _('Passwords do not match.')})
        try:
            validate_password(newPassword, self.instance)
        except ValidationError as exc:
            raise serializers.ValidationError({'newPassword': exc.messages})
        
        return data 

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.set_password(validated_data['newPassword'])
        instance.save(update_fields=['password'])
        return instance


#Custom serializer for obtaining email for password reset 
class ResetEmailSerializer(serializers.Serializer):
    email = serializers.CharField(write_only=True)

    def validate_email(self, email):
        if not User.objects.filter(email__iexact=email):
            raise serializers.ValidationError('Email is incorrect or does not exist.')
        return email 


#Custom serializer for password reset from email with token
class ResetPasswordSerializer(serializers.Serializer):  
    # uid = serializers.CharField(write_only=True, required=False)
    # token = serializers.CharField(write_only=True, required=False) 
    newPassword = serializers.CharField(write_only=True)
    newPassword2 = serializers.CharField(write_only=True)

    def validate(self, data):
        #Get keyword args from view (passed from context)
        view_kwargs = getattr(self.context.get('view'), 'kwargs', {})

        #Extract uid and token
        uid = view_kwargs.get('uidb64')
        token = view_kwargs.get('token')
        
        #Extract passwords from received data 
        newPassword = data.get('newPassword')
        newPassword2 = data.get('newPassword2')

        if not newPassword:
            raise serializers.ValidationError({'newPassword': _('New password is required.')})
        if not newPassword2:
            raise serializers.ValidationError({'newPassword2': _('Password confirmation is required.')})
        if newPassword != newPassword2:
            raise serializers.ValidationError({'newPassword2': _('Passwords do not match.')})
        
        try:
            #decode identifier to get user 
            user_id = force_str(urlsafe_base64_decode(uid))
            
            #save user for later update/saving
            self.user = User.objects.get(pk=user_id)

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({'uid': _('Invalid reset link.')})
        
        if not default_token_generator.check_token(self.user, token):
            raise serializers.ValidationError({'token': _('Invalid or expired reset token.')})
        
        try:
            validate_password(newPassword, self.user)
        except ValidationError as exc:
            raise serializers.ValidationError({'newPassword': exc.messages})
        
        data['uid'] = uid 
        data['token'] = token
        data['name'] = self.user.name
        data['email'] = self.user.email
        return data 
        
    @transaction.atomic
    def save(self, **kwargs):
        self.user.set_password(self.validated_data['newPassword'])
        self.user.save(update_fields=['password'])
        return self.user
    