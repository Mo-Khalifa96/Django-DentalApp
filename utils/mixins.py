from clinic.models import Branch
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from utils.validators import validate_uuid


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


#Validate branch mixin -- used with `create` serializers
class ValidateBranchMixin:
    def validate_branchId(self, branch):
        if not branch:
            #use user's currently active branch
            user = self.context['request'].user
            if user.branch:
                return user.branch
            elif Branch.objects.exists():
                raise serializers.ValidationError(_('Clinic branch must be provided when at least one branch is registered. Please provide a branch ID or contact the admin to assign a branch to your account.'))
        return branch


#Mixin to filter querysets by branch -- used with List views 
# if preloaded qs needs to be restricted by branch)
class FilterByBranchMixin:
    def filter_by_branch(self, queryset, branch_field='branch_id'):
        #get user
        user = self.request.user
        # branchId_qp = self.request.query_params.get('branchId')

        #filter queryset by the user's current active branch
        if getattr(user, 'branch_id', None):
            return queryset.filter(**{branch_field: user.branch_id})
        
        #return data filtered by all the branches the user belong to
        elif user.branches.exists():
            qs_filter = {f"{branch_field}__in": user.branches.values_list('id', flat=True)}
            return queryset.filter(**qs_filter)

        # #fallback -- try using the query parameter instead
        # elif branchId_qp and user.branches.filter(id=branchId_qp).exists():
        #     return queryset.filter(**{branch_field: branchId_qp})
       
       #else, check if clinic has no branches
        elif not Branch.objects.exists():
            return queryset
        
        #if none is met, return nothing to prevent data leakage
        return queryset.none()
    

#Mixin to pass branch id to serializer context -- used for /options/ endpoints
class BranchToSerializerMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        branchId = validate_uuid(self.request.query_params.get('branchId'))
        if branchId:
            try:
                Branch.objects.get(id=branchId)
            except Branch.DoesNotExist:
                raise ValidationError({'branchId': _('Branch was not found or does not exist.')})
        context['branchId'] = branchId
        return context

