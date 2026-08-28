from utils.base_views import *
from users.models import User
from clinic.models import Branch
from users.filters import UsersFilter
from users.permissions import AdminOnly
from utils.validators import validate_uuid
from rest_framework import status, generics 
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError, PermissionDenied
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from users.serializers.users import (CreateUserSerializer, ListUsersSerializer, RetrieveUserSerializer, 
                                     UpdateUserSerializer, SetActiveBranchSerializer, UsersOptionsSerializer,
                                     UserPreferencesSerializer, DefaultRolesSerializer, PermissionsSerializer)



#USERS API VIEWS 
#Create new user API view
@extend_schema(tags=['Users'])
class ListCreateUserAPIView(ListCreateAPIView):
    queryset = User.objects.select_related('branch')\
        .prefetch_related('branches').all()
    permission_classes = [AdminOnly]
    ordering = ['branch__name', 'name', '-createdAt']
    ordering_fields = ['name']
    search_fields = ['name', 'email']
    filterset_class = UsersFilter 
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ListUsersSerializer
        else:
            return CreateUserSerializer


#Retrieve user profile API view 
@extend_schema(tags=['Users'])
class RetrieveUserProfileAPIView(RetrieveAPIView):  #connects to /auth/me/ only
    queryset = User.objects.select_related('branch')\
        .prefetch_related('branches').all()
    serializer_class = RetrieveUserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


#Retrieve/Update/Delete user API view 
@extend_schema(tags=['Users'])
class RetrieveUpdateDeleteUserAPIView(RetrieveUpdateDeleteAPIView):
    queryset = User.objects.select_related('branch')\
        .prefetch_related('branches').all()
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def get_permissions(self):
        if self.request.method == 'DELETE':
            return [AdminOnly()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateUserSerializer
        else:
            return RetrieveUserSerializer
        
    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        serializer_context['user_id'] = self.kwargs['id']
        return serializer_context

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        #soft delete user
        User.objects.delete_user(request_user=request.user, user=user)
        return Response({}, status=status.HTTP_204_NO_CONTENT)
    

#API view for serving choices data 
@extend_schema(
    tags=['Users'],
    parameters=[
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveUsersOptionsAPIView(generics.GenericAPIView):
    queryset = User.objects.all()
    serializer_class = UsersOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)


########################

#User preferences API views 
@extend_schema(tags=['Users'])
class UserPreferencesAPIView(RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserPreferencesSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


########################


#Set active branch API view 
@extend_schema(tags=['Users'])
class SetActiveBranchAPIView(generics.GenericAPIView):
    queryset = User.objects.select_related('branch')\
        .prefetch_related('branches').all()
    serializer_class = SetActiveBranchSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        #get current user and branch
        user = request.user
        if 'branchId' not in request.data.keys():
            raise ValidationError({'branchId': _('Branch ID is required.')})

        #Get branch ID from request data
        branchId = validate_uuid(request.data.get('branchId'), 'branchId')
        if branchId in (None, ''):
            active_branch = None
        else:
            #Verify branch exists
            active_branch = get_object_or_404(Branch.objects.only('id'), id=branchId)

            #Verify branch belongs to the user
            if not user.branches.exists() or not user.branches.filter(id=branchId).exists():
                raise PermissionDenied(_('Permission denied. You do not belong to this branch.'))
        
        #Assign active branch
        user.branch = active_branch
        user.save(update_fields=['branch', 'updatedAt'])
        return Response({'success': True}, status=status.HTTP_200_OK)

#Proposed alternative for setting for setting only (cannot set branch to None)
@extend_schema(tags=['Users'])
class SetActiveBranchAPIView_SetOnly(generics.GenericAPIView):
    queryset = User.objects.select_related('branch')\
        .prefetch_related('branches').all()
    serializer_class = SetActiveBranchSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        #get current user and branch
        user = request.user

        branchId = request.data.get('branchId')
        if not branchId and Branch.objects.exists():
            raise ValidationError({'branchId': _('Branch ID is required to activate user branch.')})

        #Verify branch exists
        active_branch = get_object_or_404(Branch.objects.only('id'), id=branchId)

        #Verify branch belongs to the user
        if not user.branches.exists() or not user.branches.filter(id=branchId).exists():
            raise PermissionDenied(_('Permission denied. You do not belong to this branch.'))
        
        #Assign active branch
        user.branch = active_branch
        user.save(update_fields=['branch', 'updatedAt'])
        return Response({'success': True}, status=status.HTTP_200_OK)


########################


#Default roles API view
@extend_schema(tags=['Roles and Permissions'])
class DefaultRolesAPIView(GenericAPIView):
    queryset = User.objects.all()
    pagination_class = None
    serializer_class = DefaultRolesSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        #build response data
        data = [
            {
                'role': 'admin',
                'label': 'Admin',
                'description': 'Full access to all modules, operations, and settings.',
                'permissions': User.DEFAULT_ROLE_PERMISSIONS.get('admin')
            },
            {
                'role': 'dentist',
                'label': 'Dentist',
                'description': 'Default permissions include all clinical and patient records.',
                'permissions': User.DEFAULT_ROLE_PERMISSIONS.get('dentist')
            },
            {
                'role': 'receptionist',
                'label': 'Receptionist',
                'description': 'Default permissions cover some patient records, appointments, waiting room, and patient recall.',
                'permissions': User.DEFAULT_ROLE_PERMISSIONS.get('receptionist')
            },
            {
                'role': 'assistant',
                'label': 'Assistant',
                'description': 'Default permissions cover some clinical records, including inventory, lab orders, and sterilization logs, but no access to patient records.',
                'permissions': User.DEFAULT_ROLE_PERMISSIONS.get('assistant')
            },
            {
                'role': 'accountant',
                'label': 'Accountant',
                'description': 'Default permissions include access to financial records and handling of finances more generally.',
                'permissions': User.DEFAULT_ROLE_PERMISSIONS.get('accountant')
            }
        ]

        #Serializer data to return response 
        serializer = self.get_serializer(data, many=True)

        #return response
        return Response(serializer.data, status=status.HTTP_200_OK)


#Permissions API view
@extend_schema(tags=['Roles and Permissions'])
class PermissionsAPIView(GenericAPIView):
    queryset = User.objects.all()
    pagination_class = None
    serializer_class = PermissionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        #build response data
        data = [
            {
                'key': 'view.calendar',
                'label': 'View doctor appointments on dashboard',
                'module': 'Dashboard'
            },
            {
                'key': 'view.clinicalAnalytics',
                'label': 'View dashboard clinical analytics',
                'module': 'Dashboard'
            },
            {
                'key': 'view.financialAnalytics',
                'label': 'View dashboard financial analytics',
                'module': 'Dashboard'
            },
            {
                'key': 'view.waitingRoom',
                'label': 'View waiting room',
                'module': 'Waiting Room'
            },
            {
                'key': 'view.patients',
                'label': 'View patients list',
                'module': 'Patient Records'
            },
            {
                'key': 'view.patientDetail',
                'label': 'View patient profile',
                'module': 'Patient Records'
            },
            {
                'key': 'create.patient',
                'label': 'Create new patient',
                'module': 'Patient Records'
            },
            {
                'key': 'update.patient',
                'label': 'Update patient details',
                'module': 'Patient Records'
            },
            {
                'key': 'delete.patient',
                'label': 'Delete patient',
                'module': 'Patient Records'
            },
            {
                'key': 'view.visits',
                'label': 'View patient visit history',
                'module': 'Visit History'
            },
            {
                'key': 'create.visit',
                'label': 'Create new visit record',
                'module': 'Visit History'
            },
            {
                'key': 'view.appointments',
                'label': 'View appointments list',
                'module': 'Appointments'
            },
            {
                'key': 'view.appointmentDetail',
                'label': 'View appointment details',
                'module': 'Appointments'
            },
            {
                'key': 'create.appointment',
                'label': 'Create new appointment',
                'module': 'Appointments'
            },
            {
                'key': 'update.appointment',
                'label': 'Update appointment',
                'module': 'Appointments'
            },
            {
                'key': 'delete.appointment',
                'label': 'Delete appointment',
                'module': 'Appointments'
            },
            {
                'key': 'send.whatsappMessage',
                'label': 'Send WhatsApp messages to patients',
                'module': 'Appointments'
            },
            {
                'key': 'view.treatments',
                'label': 'View treatment plans list',
                'module': 'Treatment Plans'
            },
            {
                'key': 'create.treatment',
                'label': 'Create new treatment plan',
                'module': 'Treatment Plans'
            },
            {
                'key': 'update.treatment',
                'label': 'Update treatment plan',
                'module': 'Treatment Plans'
            },
            {
                'key': 'delete.treatment',
                'label': 'Delete treatment plan',
                'module': 'Treatment Plans'
            },
            {
                'key': 'view.patientInsurance',
                'label': 'View patient insurance coverage',
                'module': 'Patient Insurance',
            },
            {
                'key': 'update.patientInsurance',
                'label': 'Update patient insurance coverage',
                'module': 'Patient Insurance',
            },
            {
                'key': 'view.procedures',
                'label': 'View procedures list',
                'module': 'Procedures'
            },
            {
                'key': 'create.procedure',
                'label': 'Create new procedure',
                'module': 'Procedures'
            },
            {
                'key': 'update.procedure',
                'label': 'Update procedure',
                'module': 'Procedures'
            },
            {
                'key': 'delete.procedure',
                'label': 'Delete procedure',
                'module': 'Procedures'
            },
            {
                'key': 'view.inventory',
                'label': 'View inventory list',
                'module': 'Inventory'
            },
            {
                'key': 'create.inventory',
                'label': 'Create new inventory item',
                'module': 'Inventory'
            },
            {
                'key': 'update.inventory',
                'label': 'Update inventory item',
                'module': 'Inventory'
            },
            {
                'key': 'delete.inventory',
                'label': 'Delete inventory item',
                'module': 'Inventory'
            },
            {
                'key': 'view.labs',
                'label': 'View labs list',
                'module': 'Labs'
            },
            {
                'key': 'create.lab',
                'label': 'Create new lab',
                'module': 'Labs'
            },
            {
                'key': 'update.lab',
                'label': 'Update lab details',
                'module': 'Labs'
            },
            {
                'key': 'delete.lab',
                'label': 'Delete lab',
                'module': 'Labs'
            },
            {
                'key': 'view.labOrders',
                'label': 'View lab orders list',
                'module': 'Lab Orders'
            },
            {
                'key': 'view.labOrderDetail',
                'label': 'View lab order details',
                'module': 'Lab Orders'
            },
            {
                'key': 'create.labOrder',
                'label': 'Create new lab order',
                'module': 'Lab Orders'
            },
            {
                'key': 'update.labOrder',
                'label': 'Update lab order',
                'module': 'Lab Orders'
            },
            {
                'key': 'delete.labOrder',
                'label': 'Delete lab order',
                'module': 'Lab Orders'
            },
            {
                'key': 'view.bills',
                'label': 'View bills list',
                'module': 'Billing'
            },
            {
                'key': 'create.bill',
                'label': 'Create new bill',
                'module': 'Billing'
            },
            {
                'key': 'update.bill',
                'label': 'Update bill',
                'module': 'Billing'
            },
            {
                'key': 'delete.bill',
                'label': 'Delete bill',
                'module': 'Billing'
            },
            {
                'key': 'view.transactions',
                'label': 'View transactions list',
                'module': 'Transactions'
            },
            {
                'key': 'create.transaction',
                'label': 'Create new transaction',
                'module': 'Transactions'
            },
            {
                'key': 'delete.transaction',
                'label': 'Delete transaction',
                'module': 'Transactions'
            },
            {
                'key': 'view.invoices',
                'label': 'View invoices list',
                'module': 'Invoices'
            },
            {
                'key': 'create.invoice',
                'label': 'Create new invoice',
                'module': 'Invoices'
            },
            {
                'key': 'update.invoice',
                'label': 'Update invoice',
                'module': 'Invoices'
            },
            {
                'key': 'delete.invoice',
                'label': 'Delete invoice',
                'module': 'Invoices'
            },
            {
                'key': 'view.insuranceProviders',
                'label': 'View insurance providers list',
                'module': 'Insurance Providers'
            },
            {
                'key': 'create.insuranceProvider',
                'label': 'Create new insurance provider',
                'module': 'Insurance Providers'
            },
            {
                'key': 'update.insuranceProvider',
                'label': 'Update insurance provider details',
                'module': 'Insurance Providers'
            },
            {
                'key': 'delete.insuranceProvider',
                'label': 'Delete insurance provider',
                'module': 'Insurance Providers'
            },
            {
                'key': 'view.sterilizationLogs',
                'label': 'View sterilization logs list',
                'module': 'Sterilization Logs'
            },
            {
                'key': 'create.sterilizationLog',
                'label': 'Create new sterilization log',
                'module': 'Sterilization Logs'
            },
            {
                'key': 'update.sterilizationLog',
                'label': 'Update sterilization log',
                'module': 'Sterilization Logs'
            },
            {
                'key': 'delete.sterilizationLog',
                'label': 'Delete sterilization log',
                'module': 'Sterilization Logs'
            },
            {
                'key': 'view.recalls',
                'label': 'View patient recalls list',
                'module': 'Patient Recalls'
            },
            {
                'key': 'create.recall',
                'label': 'Create new patient recall',
                'module': 'Patient Recalls'
            },
            {
                'key': 'update.recall',
                'label': 'Update patient recall',
                'module': 'Patient Recalls'
            },
            {
                'key': 'delete.recall',
                'label': 'Delete patient recall',
                'module': 'Patient Recalls'
            },
            {
                'key': 'view.doctorSchedules',
                'label': 'View doctor schedules',
                'module': 'Doctor Schedules'
            },
            {
                'key': 'view.settings',
                'label': 'View account settings',
                'module': 'Settings'
            }
        ]

        #Serializer data to return response 
        serializer = self.get_serializer(data, many=True)

        #return response
        return Response(serializer.data, status=status.HTTP_200_OK)

