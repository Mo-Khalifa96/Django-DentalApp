from users.models import User
from clinic.models import Branch
from rest_framework import serializers
from patients.models import Appointment
from utils.mixins import UserPermissionsMixin
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from clinic.docs import dashboard_stats_schema, dashboard_options_schema


#DASHBOARD SERIALIZERS 
#Dashboard Statistics serializer
@dashboard_stats_schema
class DashboardStatisticsSerializer(UserPermissionsMixin, serializers.Serializer):
    patientsTotal = serializers.IntegerField()  #new 
    patientsNew = serializers.IntegerField()   #monthly by default -- is newPatientsThisMonth
    appointmentsCount = serializers.IntegerField()
    appointmentsCompleted = serializers.IntegerField()  #monthly by default
    revenue = serializers.FloatField()  #monthly by default -- taken from 'paid' field on Visits model
    outstanding = serializers.FloatField()  #new -- total not paid
    # currency = serializers.CharField(allow_blank=True, allow_null=True)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        #Revenue and outstanding should not be shown to non-Admin users 
        if getattr(request.user, 'role', None) != 'admin':
            fields.pop('revenue', None)
            fields.pop('outstanding', None)
            # fields.pop('currency', None)
        return fields

#serializer for validating query parameters to dashboard/stats/
class DashboardQueryParamSerializer(serializers.Serializer):
    branchId = serializers.UUIDField(required=False, allow_null=True)
    dateRange = serializers.ChoiceField(choices=(('today', 'today'), ('week', 'week'), ('month', 'month')),
                                        required=False, allow_blank=True)


#Dashboard Appointments Today serializer
class DashboardAppointmentTodaySerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    patientName = serializers.CharField(source='patient.name', read_only=True)
    doctorId = serializers.PrimaryKeyRelatedField(source='doctor', read_only=True)
    # doctorName = serializers.CharField(source='doctor.name', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True, allow_null=True)

    class Meta:
        model = Appointment
        fields = ['id', 'patientId', 'patientName', 'doctorId', 'doctorName', 
                  'branchId', 'startTime', 'endTime', 'type', 'room', 'status']



#Serializer for serving choices for dashboard filtering
@dashboard_options_schema
class DashboardOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    doctorChoices = serializers.SerializerMethodField()
    
    #Get branch choices (with id and name)
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_branchChoices(self, obj):
        return [
                {'branchId': branch_id, 'name': name} 
                    for branch_id,name in Branch.objects\
                    .values_list('id', 'name').order_by('name')
                ]

    #Get doctors list (with id and name)
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_doctorChoices(self, obj):
        branchId = self.context.get('branchId')
        filters = {'branch_id': branchId, 'role__in': ['dentist', 'admin']} if branchId else {'role__in': ['dentist', 'admin']}

        return [
                {'doctorId': doctor_id, 'doctorName': name}
                 for doctor_id,name in User.objects.only('id','name','role', 'branch')\
                    .filter(**filters).values_list('id', 'name').order_by('name')
            ]
