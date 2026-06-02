
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend


#Helper custom filters
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


#Custom filter backend for taking optional parameters from view
class CustomDjangoFilterBackend(DjangoFilterBackend):
    def get_filterset_kwargs(self, request, queryset, view):
        kwargs = super().get_filterset_kwargs(request, queryset, view)
        if hasattr(view, 'get_extra_filterset_kwargs'):
            kwargs.update(view.get_extra_filterset_kwargs())
        return kwargs

