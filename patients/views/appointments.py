from utils.base_views import * 
from django.conf import settings
from django.db import transaction
from django_q.models import Schedule
from patients.models import Appointment
from rest_framework import status, generics
from rest_framework.response import Response
from users.utils import get_required_permission
from patients.filters import AppointmentsFilter
from rest_framework.filters import SearchFilter
from utils.filters import CustomOrderingFilter
from utils.mixins import BranchToSerializerMixin
from users.permissions import PatientDataPermissions
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from services.whatsapp.tasks import schedule_appointment_reminder
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.appointments import (AppointmentSerializer, RetrieveAppointmentSerializer,
                                              CreateAppointmentSerializer, UpdateAppointmentSerializer,
                                              CancelAppointmentSerializer, AppointmentOptionsSerializer)


#APPOINTMENTS API VIEWS
#List appointments API view 
@extend_schema(tags=['Appointments'])
class ListCreateAppointmentsAPIView(FilterListCreateAPIView):
    permission_classes = [PatientDataPermissions]
    ordering = ['branch__name', '-date', 'startTime', 'endTime']  #default order of fields
    ordering_fields = ['date', 'startTime', 'endTime', 'status']  
    search_fields = ['patient__name', 'doctor__name', 'procedure__name', 'room']
    filterset_class = AppointmentsFilter
    filter_backends = [DjangoFilterBackend, CustomOrderingFilter, SearchFilter]

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('appointments', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #fetch appointments queryset
        appointments = Appointment.objects.select_related(
                'patient', 'doctor', 'procedure', 'branch'
            ).all()
        
        if self.request.method == 'POST':
            return appointments

        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return appointments
        
        elif getattr(user, 'role', None) == 'dentist':
            return appointments.filter(doctor=user)
        
        elif getattr(user, 'role', None) == 'receptionist' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            #filter queryset by branch 
            return self.filter_by_branch(appointments)
        else:
            return appointments.none()
    
    def paginate_queryset(self, queryset):
        self.paginator.page_size = 50
        return super().paginate_queryset(queryset)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateAppointmentSerializer
        return AppointmentSerializer

    def perform_create(self, serializer):
        #save to db and get appointment instance 
        appointment = serializer.save()

        #schedule appointment reminder
        if settings.ENABLE_AUTOMATED_REMINDERS:
            #create scheduled task with the reminder 
            transaction.on_commit(
                lambda: schedule_appointment_reminder(appointment)
            )


#Retrieve/Update appointment API view
@extend_schema(tags=['Appointments'])
class RetrieveUpdateCancelAppointmentAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_field = 'id'
    lookup_url_kwarg = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('appointments', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        if self.request.method == 'GET':
            return Appointment.objects.select_related(
             'patient', 'doctor', 'procedure', 'branch').all()
        return Appointment.objects.select_related('branch').all()

    def get_serializer_class(self):
        req_method = self.request.method 
        if req_method == 'GET':
            return RetrieveAppointmentSerializer
        elif req_method in ('PUT', 'PATCH'):
            return UpdateAppointmentSerializer
        elif req_method == 'DELETE':
            return CancelAppointmentSerializer

    @transaction.atomic 
    def delete(self, request, *args, **kwargs):
        appointment = self.get_object()

        #set appointment status as cancelled 
        appointment.status = 'cancelled'

        #Set patient's nextAppointment to None
        appointment.patient.nextAppointment = None
        appointment.patient.save(update_fields=['nextAppointment', 'updatedAt'])

        #get reason from serializer and return response
        serializer = self.get_serializer(data=getattr(request, 'data', {}))
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason')
        if reason:
            appointment.notes = reason 
        appointment.save(update_fields=['status', 'notes', 'updatedAt'])

        #Cancel scheduled reminder
        if settings.ENABLE_AUTOMATED_REMINDERS:
            Schedule.objects.filter(
                name=f'Schedule reminder for appointment {appointment.id}'
            ).delete()

        return Response({'message': _('Appointment cancelled successfully.')}, status=status.HTTP_200_OK)


#API View for serving choice options for appointment creation
@extend_schema(
    tags=['Appointments'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveAppointmentOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = AppointmentOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)  #context=self.get_serializer_context()
