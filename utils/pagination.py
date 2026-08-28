from rest_framework.response import Response 
from users.utils import get_category_from_url
from rest_framework.pagination import PageNumberPagination, CursorPagination


#Define custom page paginator (with permissions)
class CustomPageNumberPagination(PageNumberPagination):
    page_size = 25
    page_query_param = 'page'
    page_size_query_param = 'limit' 
    max_page_size = 100

    def get_paginated_response(self, data):
        #Get user permissions
        user_permissions = 'N/A'
        if self.request and self.request.user:
            category = get_category_from_url(self.request)
            user_permissions = self.request.user.get_user_permissions(category)

        return Response({
            'success': True,
            'data': data, 
            'pagination': {
                'page': self.page.number,
                'limit': self.page_size,
                'total': self.page.paginator.count,    
                'totalPages': self.page.paginator.num_pages,
                'hasNext': self.page.has_next(),
                'hasPrev': self.page.has_previous(),
            },
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'metadata': {
                'userPermissions': user_permissions
            }
        })


#Custom page paginator for dashboard appointments-today
class DashboardAppointmentsPagination(PageNumberPagination):
    page_size = 50
    page_query_param = 'page'
    page_size_query_param = 'limit'
    max_page_size = 200

    def get_paginated_response(self, data):
        #Get user permissions
        user_permissions = 'N/A'
        if self.request and self.request.user:
            user_permissions = self.request.user.get_user_permissions()  #defaults/sidebar perms

        return Response({
            'success': True,
            'data': data,
            'metadata': {
                'userPermissions': user_permissions
            }
        })

#Custom page paginator for patient treatment plans
class TreatmentPlansPagination(PageNumberPagination):
    page_size = 50
    page_query_param = 'page'
    page_size_query_param = 'limit'
    max_page_size = 200

    def get_paginated_response(self, data):
        #Get user permissions
        user_permissions = 'N/A'
        if self.request and self.request.user:
            user_permissions = self.request.user.get_user_permissions('treatment-plans')

        return Response({
            'success': True,
            'data': data,
            'metadata': {
                'userPermissions': user_permissions
            }
        })


#Define a custom cursor paginator for whatsapp messages
class MessagesHistoryPaginator(CursorPagination):
    page_size = 10
    ordering = '-createdAt'
    cursor_query_param = 'cursor'

    def get_paginated_response(self, data):
        #Get user permissions
        user_permissions = 'N/A'
        if self.request and self.request.user:
            user_permissions = self.request.user.get_user_permissions()  #defaults/sidebar perms
            user_permissions['send.whatsappMessage'] = 'send.whatsappMessage' in getattr(self.request.user, 'userPermissions', [])

        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'pageSize': self.page_size,
                'hasNext': self.has_next,
                'hasPrevious': self.has_previous,
            },
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            },
            'metadata': {
                'userPermissions': user_permissions
            }
        })
