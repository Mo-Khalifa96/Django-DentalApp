import logging
from clinic.models import Branch
from django.conf import settings
from rest_framework.permissions import BasePermission
from django.core.exceptions import ImproperlyConfigured


#Initiate logger 
logger = logging.getLogger(__name__)

#Base permission class 
class SystemBasePermission(BasePermission):
    def has_permission(self, request, view):
        #basic user authentication
        if not request.user or not request.user.is_authenticated:
            return False
        return True
    
    def has_object_permission(self, request, view, obj):
        #admin gets full access
        if request.user.role == 'admin':
            return True 

        #authenticate by branch for non-admins
        if Branch.objects.exists():
            if hasattr(obj, 'branch_id') and getattr(obj, 'branch_id', None):
                return request.user.branches.filter(id=obj.branch_id).exists()

            elif hasattr(getattr(obj, 'patient', None), 'branch_id'):
                return request.user.branches.filter(id=obj.patient.branch_id).exists()
            
            elif hasattr(getattr(obj, 'doctor', None), 'branch_id'):
                return request.user.branches.filter(id=obj.doctor.branch_id).exists()
        
        return True 
        

#Admin only permission
class AdminOnly(SystemBasePermission):
    def has_permission(self, request, view):
        #call parent's has_permission() for basic authentication
        if super().has_permission(request, view):
            if request.user.role == 'admin':
                return True 
        return False
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


#Dentist only permission
class DoctorSchedulePermissions(SystemBasePermission):
    def has_permission(self, request, view):
        #call parent's has_permission() for basic authentication
        if super().has_permission(request, view):
            if request.user.role in ('admin', 'dentist'):
                return True 
        return False

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        if hasattr(obj, 'doctor'):
            return obj.doctor == request.user 
        elif hasattr(obj, 'schedule') and obj.schedule:
            return obj.schedule.doctor == request.user
        return False 


#Waiting room permission class
class WaitingRoomPermission(SystemBasePermission):
    def has_permission(self, request, view):
        if super().has_permission(request, view):
            if request.user.role == 'admin' or \
             request.user.has_special_permission('view.waitingRoom'):
                return True
        return False
    
    def has_object_permission(self, request, view, obj):
        return super().has_object_permission(request, view, obj)


#Dentist of patient only permission
class DentistOfPatientOnly(SystemBasePermission):
    def has_permission(self, request, view):
        if super().has_permission(request, view):
            if request.user.role in ('admin', 'dentist'):
                return True 
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
class SystemUserPermissions(SystemBasePermission):
    '''
    Generic permission class that gets the required permission from the view 
    and checks it against user assigned permissions.
    '''

    def has_permission(self, request, view):
        if settings.DEBUG:  #TODO - remove when ready
            if not hasattr(view, 'required_permission'):
                raise ImproperlyConfigured('Permission class inapplicable to view:', view)
        
        #call parent's has_permission() for basic authentication
        if not super().has_permission(request, view):
            return False
        
        #admin always permitted 
        if request.user.role == 'admin':
            return True
    
        #Get required permission from view (if any)
        required_permission = getattr(view, 'required_permission', None)
        if required_permission:
            return request.user.has_special_permission(required_permission)
        
        return False
    
    def has_object_permission(self, request, view, obj):
        #call parent's has_object_permission() for branch permission
        return super().has_object_permission(request, view, obj)


#Permissions subclass from SystemUserPermissions to control access to patients' data 
class PatientDataPermissions(SystemUserPermissions):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True 

        if request.user.role != 'dentist':
            #return branch permission for non-admins/dentists
            return super().has_object_permission(request, view, obj)

        if hasattr(obj, 'doctor') and obj.doctor:
            return obj.doctor == request.user 
        elif hasattr(obj, 'patient') and obj.patient:
            return obj.patient.doctor == request.user
        else:
            #fallback to has_permission() check
            # logger.warning(
            #     f'Could not determine object permission for {obj}for request:\n',
            #     f'{request}\n\nDefaulting to has_permission().')
            return self.has_permission(request, view)

