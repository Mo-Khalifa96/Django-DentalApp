from clinic.models import Branch
from utils.validators import validate_uuid
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import FilterSet


#Helper custom filters
#Base filterset class with custom branch filter method -- for choice filters
class BaseFilterSet(FilterSet):
    '''A base FilterSet for providing branch filter based on the request user.'''

    def get_branch_filter(self):
        if not self.request or not hasattr(self.request, 'user'):
            return None
        
        #get current request user 
        user = self.request.user 

        #assign branch query (if provided)
        branchId = validate_uuid(self.request.query_params.get('branchId'))

        #return filter
        if branchId:
            #return branch from query param
            return {'branch_id': branchId}
        elif getattr(user, 'role', None) == 'admin'\
         or not Branch.objects.exists():
            return {}  #no filtering
        elif getattr(user, 'branch_id', None):
            #use current user's active branch
            return {'branch_id': user.branch_id}
        else:
            #include all branches the user belong to 
            branch_ids_list = user.branches.values_list('id', flat=True)

            #return filter or None if user has no branches and branches exist
            return {'branch_id__in': branch_ids_list} if branch_ids_list else None

        

#Custom ordering/sorting filter for list views (general)
class CustomOrderingFilter(OrderingFilter):
    ordering_param = 'sortBy'

    def get_ordering(self, request, queryset, view):
        sort_by = request.query_params.get('sortBy')
        sort_order = request.query_params.get('sortOrder', 'asc')

        if sort_by:
            # validate against allowed fields
            allowed = getattr(view, 'ordering_fields', [])
            if sort_by in allowed:
                return [f'-{sort_by}' if sort_order == 'desc' else sort_by]
        
        #fall back to default ordering
        return self.get_default_ordering(view)

