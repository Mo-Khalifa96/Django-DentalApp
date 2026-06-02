from users.models import User
from clinic.models import Branch
from urllib.parse import urlparse
from django.db import transaction
from rest_framework import serializers
from django.core.exceptions import ValidationError
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from django.contrib.auth.password_validation import validate_password
from users.docs import permissions_field_schema, retrieve_user_schema, update_user_schema, users_options_schema


#USERS SERIALIZERS
#Create user serializer 
class CreateUserSerializer(serializers.ModelSerializer, ValidateBranchMixin):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'specialization', 'branchId', 'avatar', 
                  'password', 'password2', 'createdAt']
        read_only_fields = ['id', 'createdAt']
        extra_kwargs = {'specialization': {'required': False},  'avatar': {'required': False},
                        'branchId': {'required': False}}
    
    def validate(self, data):
        '''Validates passwords during user creation.'''
        password = data.get('password')
        password2 = data.get('password2')

        if not password or not password2:
            raise serializers.ValidationError({'password2': _('Both password fields are required.')})
        if password != password2:
            raise serializers.ValidationError({'password2': _('Passwords do not match.')})
        try:
            #validate password 
            validate_password(password)
        except ValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        
        return data 

    @transaction.atomic 
    def create(self, validated_data):
        #handle user's password 
        password = validated_data.pop('password', None)   #get password
        validated_data.pop('password2', None)   #Remove password 2 

        #Create new user 
        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user 

#List users serializer 
class ListUsersSerializer(serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'specialization', 'branchId', 'isActive', 'createdAt']


#Retrieve user profile serializer 
@retrieve_user_schema
class RetrieveUserSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    avatar = serializers.ImageField(use_url=True, read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)

    class Meta: 
        model = User
        fields = ['id', 'email', 'name', 'role', 'specialization',  'branchId', 
                  'avatar', 'permissions', 'isActive', 'createdAt']

    @permissions_field_schema
    def get_permissions(self, obj):   
        return {
            permission: permission in obj.userPermissions 
            for permission in User.USER_PERMISSIONS
        } 

    def get_fields(self):
        fields = super().get_fields()
        user = self.context.get('request').user
        #Permissions not shown to non-Admin users
        if getattr(user, 'role', None) != 'admin':
            fields.pop('permissions', None)
        return fields


#Update user serializer 
@update_user_schema
class UpdateUserSerializer(serializers.ModelSerializer):
    currentPassword = serializers.CharField(write_only=True, required=False, allow_blank=True)
    newPassword = serializers.CharField(write_only=True, required=False, allow_blank=True)
    newPassword2 = serializers.CharField(write_only=True, required=False, allow_blank=True)
    avatar = serializers.ImageField(use_url=True, required=False, allow_empty_file=True)
    permissions = serializers.DictField(child=serializers.BooleanField(required=False), required=False, allow_empty=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'currentPassword', 'newPassword', 'newPassword2', 'name', 'role', 
                  'specialization', 'branchId', 'avatar', 'permissions', 'isActive', 'updatedAt']
        read_only_fields = ['id', 'updatedAt']
        extra_kwargs = {field: {'required': False} for field in 
            ('email', 'currentPassword', 'newPassword', 'newPassword2', 'name', 'role', 'specialization',
             'branchId', 'avatar', 'permissions', 'isActive')
            }

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        user_id = self.context.get('user_id', None)

        #Role and permission not shown to non-Admin users 
        if getattr(request.user, 'role', None) != 'admin':
            fields.pop('role', None)
            fields.pop('permissions', None)
            fields.pop('branch', None)

        #Prevent user/admin from changing another's password
        if getattr(request.user, 'id', None) != user_id:
            fields.pop('currentPassword')
            fields.pop('newPassword')
            fields.pop('newPassword2')

        return fields
    

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['permissions'] = {
            permission: permission in instance.userPermissions 
            for permission in User.USER_PERMISSIONS
            }
        
        return rep

    def to_internal_value(self, data):
        '''Parses nested serializers data if passed as JSON strings.'''
        #Use copy because original is immutable 
        data = data.copy()
        
        if (data.get('avatar', None) in (None, '', 'null')) or \
            ((self.instance.avatar and isinstance(data['avatar'], str)
              and
             urlparse(data['avatar']).path == self.instance.avatar.url)):
                data.pop('avatar', None)
    
        return super().to_internal_value(data) 
    
    #Validate passwords
    def validate(self, data):
        #obtain passwords passed (if any)
        currentPassword = data.get('currentPassword', None)
        newPassword = data.get('newPassword', None)
        newPassword2 = data.get('newPassword2', None)

        if currentPassword and newPassword:
            if not self.instance.check_password(currentPassword):
                raise serializers.ValidationError({'currentPassword': _('Current password is incorrect.')})
            if not newPassword2:
                raise serializers.ValidationError({'newPassword2': _('Password confirmation is required to change password.')})
            if currentPassword == newPassword:
                raise serializers.ValidationError({'newPassword': _('New password must be different from the old one.')})
            if newPassword != newPassword2:
                raise serializers.ValidationError({'newPassword2': _('Passwords do not match.')})
            try:
                validate_password(newPassword)
            except ValidationError as exc:
                raise serializers.ValidationError({'newPassword': exc.messages})
        
        elif newPassword and not currentPassword:
            raise serializers.ValidationError({'currentPassword': _('You must pass current password before changing it.')})
        
        return data 
    
    @transaction.atomic 
    def update(self, instance, validated_data):
        #handle passwords, permissions, & avatar 
        validated_data.pop('currentPassword', None)
        validated_data.pop('newPassword2', None)
        newPassword = validated_data.pop('newPassword', None)
        assigned_permissions = validated_data.pop('permissions', None)

        #Track fields to update 
        update_fields = []

        #Update basic fields
        for field, value in validated_data.items():
            if hasattr(instance, field) and value:
                setattr(instance, field, value)
                update_fields.append(field)

        #Hash password (if updated)
        if newPassword:
            instance.set_password(newPassword)
            update_fields.append('password')
        
        #Handle user permission updates
        if assigned_permissions:
            user_permissions_lst = instance.userPermissions
            allowed_permissions = {perm_key for perm_key,bool_val in assigned_permissions.items() if bool_val}
            disallowed_permissions = {perm_key for perm_key,bool_val in assigned_permissions.items() if not bool_val}

            #Determine added and removed permissions
            added_permissions = allowed_permissions.difference(set(user_permissions_lst))
            removed_permissions = set(user_permissions_lst).intersection(disallowed_permissions)

            #Add new allowed permissions 
            if added_permissions:
                instance.userPermissions = user_permissions_lst + list(added_permissions)
                update_fields.append('userPermissions')

            #remove disallowed permissions 
            if removed_permissions:
                instance.userPermissions = list(set(user_permissions_lst).difference(removed_permissions))
                if 'userPermissions' not in update_fields:
                    update_fields.append('userPermissions')
        
        #update user 
        update_fields.append('updatedAt')
        instance.save(update_fields=update_fields)
        return instance 


#Serializer for serving choices for dashboard filtering
@users_options_schema
class UsersOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    roleChoices = serializers.SerializerMethodField()
    
    #Get branch choices (with id and name)
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_branchChoices(self, obj):
        return [
                {'branchId': branch_id, 'name': name} 
                    for branch_id,name in Branch.objects\
                    .values_list('id', 'name').order_by('name')
                ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_roleChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in User.UserRoles
        ]
    

