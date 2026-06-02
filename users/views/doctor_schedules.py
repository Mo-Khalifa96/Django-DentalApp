from datetime import date
from utils.base_views import *
from rest_framework import status, generics 
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.filters import SearchFilter
from users.filters import DoctorSchedulesFilter
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.mixins import BranchToSerializerMixin
from users.models import User, DoctorSchedule, DoctorScheduleException
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from users.serializers.doctor_schedules import (DoctorScheduleSerializer, DoctorExceptionsSerializer,
                                                DoctorScheduleOptionsSerializer)


#DOCTOR SCHEDULES API VIEWS
#List doctors schedules API view
@extend_schema(tags=['Doctor Schedules'])
class ListDoctorsSchedulesAPIView(FilterListAPIView):
    serializer_class = DoctorScheduleSerializer
    permissions_class = [IsAuthenticated] #TODO - what are the permissions here?
    ordering = ['doctor__name', '-startTime']
    search_fields = ['doctor__name']
    filterset_class = DoctorSchedulesFilter
    filter_backend = [DjangoFilterBackend, SearchFilter]


    def get_queryset(self):
        #Get current user
        user = self.request.user 
        
        #Fetch doctor schedules list 
        schedules = DoctorSchedule.objects.select_related('doctor')\
                        .prefetch_related('exceptions').all()
        
        #provide admin with full query
        if getattr(user, 'role', None) == 'admin':
            return schedules
        
        #filter using the mixin and return results
        return self.filter_by_branch(schedules, branch_field='doctor__branch_id')


#Create/Retrieve/Update/Delete doctor schedule API view
@extend_schema(tags=['Doctor Schedules'])
class CRUD_DoctorScheduleAPIView(CreateAPIView, RetrieveUpdateDeleteAPIView):
    queryset = DoctorSchedule.objects.select_related('doctor')\
        .prefetch_related('exceptions').all()
    serializer_class = DoctorScheduleSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'doctorId'
    lookup_field = 'doctor__id'

    def get_doctor(self):
        doctor = get_object_or_404(User.objects.only('id'),
                  id=self.kwargs.get('doctorId'))
        #check object permission and return doctor object
        # self.check_object_permissions(self.request, doctor)
        return doctor

    def create(self, request, *args, **kwargs):   #TODO - test functionality against current handler
        #Check the doctor's id exists before running the request
        doctor = self.get_doctor()
        #verify the present doctor doesn't already have a schedule
        if DoctorSchedule.objects.filter(doctor_id=doctor.id).exists():
            raise ValidationError({'doctorId': _('A schedule already exists for this doctor.')})
        
        #call the parent create() method to create schedule
        return super().create(request, *args, **kwargs)
 
    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method == 'POST':
            #pass doctor id to the serializer
            context['doctor_id'] = self.kwargs.get('doctorId')
        return context


#Create schedule exception API view 
@extend_schema(tags=['Doctor Schedules'])
class CreateScheduleExceptionAPIView(CreateAPIView):
    queryset = DoctorScheduleException.objects.all()
    serializer_class = DoctorExceptionsSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'doctorId'
    lookup_field = 'schedule__doctor__id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        #pass schedule id to the serializer
        schedule = get_object_or_404(
            DoctorSchedule.objects.only('id'),
            doctor_id=self.kwargs.get('doctorId')
         )
        context['schedule_id'] = schedule.id
        return context


#Delete schedule exception API view 
@extend_schema(tags=['Doctor Schedules'])
class DeleteScheduleExceptionAPIView(DeleteAPIView):
    queryset = DoctorScheduleException.objects\
     .select_related('schedule', 'schedule__doctor').all()
    serializer_class = DoctorExceptionsSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'doctorId'
    lookup_field = 'schedule__doctor__id'

    #Override get_object() for custom lookup
    def get_object(self):
        date_from_url = self.kwargs.get('date')
        try:
            date_parsed = date.fromisoformat(date_from_url)  #expects YYYY-MM-DD
            schedule_exception = get_object_or_404(self.get_queryset(), 
                schedule__doctor__id=self.kwargs.get('doctorId'), date=date_parsed
             )
        except ValueError:
            raise ValidationError({'date': _('Invalid date format. Expected YYYY-MM-DD.')})
        # self.check_object_permissions(self.request, schedule_exception)
        return schedule_exception


#API View for serving optional choices data
@extend_schema(
    tags=['Doctor Schedules'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveDoctorSchedulesOptionsAPIView(generics.GenericAPIView, BranchToSerializerMixin):
    queryset = DoctorSchedule.objects.all()
    serializer_class = DoctorScheduleOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
