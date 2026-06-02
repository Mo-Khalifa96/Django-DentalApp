import logging
from django.conf import settings
from services.models import Message
from clinic.models import Procedure, Inventory
from rest_framework.permissions import BasePermission
from django.core.exceptions import ImproperlyConfigured


#Initiate logger 
logger = logging.getLogger(__name__)


#Admin only permission
class AdminOnly(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated: 
            if request.user.role != 'admin':
                return False 
            else:
                return True
        else:
            return False 
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


#Admin or receptionist only permission -- for waiting room
class AdminOrReceptionist(BasePermission):
    def has_permission(self, request, view):
        if request.user or request.user.is_authenticated:
            if request.user.role in ('admin', 'receptionist'):
                return True
        return False
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


#Dentist of patient only permission
class DentistOfPatientOnly(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated: 
            if request.user.role not in ('admin', 'dentist'):
                return False 
            else:
                return True
        else:
            return False 
    
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True 
        if hasattr(obj, 'doctor'):
            return obj.doctor == request.user 
        elif hasattr(obj, 'patient') and obj.patient:
            return obj.patient.doctor == request.user
        return False 


#System user-specific permission class with view-level permission mapping
class SystemUserPermissions(BasePermission):
    '''
    Generic permission class that gets the required permission from the view and checks
    it against user assigned permissions.
    '''

    def has_permission(self, request, view):
        if settings.DEBUG:  #TODO - remove when ready
            if  not hasattr(view, 'required_permission'):
                raise ImproperlyConfigured('Permission class inapplicable to view:', view)
            
        if not request.user or not request.user.is_authenticated:
            return False
        elif request.user.role == 'admin':
            return True
    
        #Get required permission from view (if any)
        required_permission = getattr(view, 'required_permission', None)
        if required_permission:
            return request.user.has_special_permission(required_permission)
        return False
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


#Permissions subclass from SystemUserPermissions to control access to patients' data 
class PatientDataPermissions(SystemUserPermissions):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True 
        if request.user.role != 'dentist' or \
         isinstance(obj, (Procedure, Inventory, Message)):
            return True   #self.has_permission(request, view) -- already passed

        if hasattr(obj, 'doctor'):
            return obj.doctor == request.user 
        elif hasattr(obj, 'patient') and obj.patient:
            return obj.patient.doctor == request.user
        else:
            #fallback to has_permission() check
            logger.warning(f'Could not determine object permission for {obj}for request:\n{request}\n\nDefaulting to has_permission().')
            return self.has_permission(request, view)

