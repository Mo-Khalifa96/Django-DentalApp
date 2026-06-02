from clinic.models import Branch
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


#Permissions mixin for serializers
class UserPermissionsMixin:
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        is_listView = self.context.get('view').get_view_name().startswith('List')

        if request and request.method == 'GET' and not is_listView:  #lists are handled by the pagination class
            data['metadata'] = {
                'userPermissions': request.user.get_user_permissions()  #non-list views use default permissions only
            }
        return data


#Response mixin for custom response structure
class ResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        is_listView = self.get_view_name().startswith('List')

        #Handle only success responses (2xx)
        if 200 <= response.status_code < 300 and response.data and not is_listView:   #lists are handled by the pagination class
            metadata = response.data.pop('metadata', None)
            response.data = {
                'success': True,
                'data': response.data
            }
            
            #add metadata (if found)
            if metadata:
                response.data['metadata'] = metadata

        return response


#Validate branch mixin -- to serializers 
class ValidateBranchMixin:
    def validate_branchId(self, branch):
        print("VALIDATION METHOD TRIGGERED!")   #TODO - test this function
        if not branch:
            user = self.context['request'].user
            if user.branch:
                return user.branch
            elif Branch.objects.exists():
                raise serializers.ValidationError(_('Clinic branch must be provided when at least one branch is registered. Please provide a branch ID or contact the admin to assign a branch to your account.'))
        return branch


#Mixin to pass branch id to serializer context
class BranchToSerializerMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        branchId = self.request.query_params.get('branchId', None)
        if branchId:
            try:
                Branch.objects.get(id=branchId)
            except Branch.DoesNotExist:
                raise ValidationError({'branchId': _('Branch was not found or does not exist.')})
        context['branchId'] = branchId
        return context


#Mixin to pass branch id to filter using custom method
class BranchToFilterMixin:
    def get_extra_filterset_kwargs(self):
        if self.request.method == 'GET': #and getattr(user, 'role', None) != 'admin':
            user = self.request.user 
            branchId = self.request.query_params.get('branchId')
            if branchId:
                branch_id = branchId
            else:
                branch_id = getattr(user.branch, 'id', None) if user.branch else None
            return {
                'branch_id': branch_id
            }
        return None


#Mixin to filter querysets by branch -- used with List views
class FilterByBranchMixin:
    def filter_by_branch(self, queryset, branch_field='branch_id'):
        #get user
        user = self.request.user
        
        #get branch from query params
        branchId = self.request.query_params.get('branchId')
        
        if branchId:
            #verify branch exists then filter by branch
            get_object_or_404(Branch.objects.only('id'), id=branchId)
            return queryset.filter(**{branch_field: branchId})
        
        #otherwise, try filtering by the user's branch
        elif getattr(user, 'branch_id', None):
            return queryset.filter(**{branch_field: user.branch_id})
       
       #else, check if clinic has no branches
        elif Branch.objects.count() == 0:
            return queryset
        
        #if none is met, return nothing to prevent data leakage
        return queryset.none()
    
