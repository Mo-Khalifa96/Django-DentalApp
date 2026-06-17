from django.db import transaction
from rest_framework import serializers
from utils.mixins import UserPermissionsMixin
from clinic.models import Branch, WorkingDaysLookUp
from utils.swagger_utils import extend_schema_field
from users.docs import doctor_schedules_options_schema
from django.utils.translation import gettext_lazy as _
from users.models import User, DoctorSchedule, DoctorScheduleException
from services.translation.serializers import TranslatedChoiceField


#DOCTOR SCHEDULES SERIALIZERS 
#Doctor exceptions serializer -- nested serializer 
class DoctorExceptionsSerializer(serializers.ModelSerializer):
    type = TranslatedChoiceField(choices=DoctorScheduleException.ExceptionTypeChoices.choices)

    class Meta:
        model = DoctorScheduleException
        fields = ['date', 'type', 'note']
        extra_kwargs = {'note': {'required': False}}

    @transaction.atomic
    def create(self, validated_data):
        #get schedule id from context
        schedule_id = self.context['schedule_id']
        #create schedule exception
        exception = DoctorScheduleException.objects\
         .create(**validated_data, schedule_id=schedule_id)
        return exception


#Base doctor schedules serializer
class DoctorScheduleSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    doctorName = serializers.CharField(source='doctor.name', read_only=True)
    doctorId = serializers.PrimaryKeyRelatedField(source='doctor', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    workingDays = serializers.ListField(child=TranslatedChoiceField(choices=WorkingDaysLookUp.choices), allow_empty=False)
    exceptions = DoctorExceptionsSerializer(many=True, required=False, allow_empty=True)

    class Meta:
        model = DoctorSchedule
        fields = ['id', 'doctorId', 'doctorName', 'branchId', 'workingDays', 'startTime', 
                  'endTime', 'breakStart', 'breakEnd', 'exceptions']
        read_only_fields = ['id', 'doctorId', 'doctorName', 'branchId']

    def validate_workingDays(self, value):
        if value:
            #remove duplicates (if any)
            value = sorted(set(value))
        return value

    @transaction.atomic
    def create(self, validated_data):
        #Extract exceptions list (if provided)
        exceptions = validated_data.pop('exceptions', [])

        #Get doctor from serializer context
        validated_data['doctor_id'] = self.context.get('doctor_id')

        #Add doctor's branch
        user = self.context.get('request').user
        validated_data['branch'] = getattr(user, 'branch', None)

        #Create doctor schedule 
        schedule = DoctorSchedule.objects.create(**validated_data)

        #Bulk create associated exceptions (if any)
        if exceptions:
            DoctorScheduleException.objects.bulk_create([
                DoctorScheduleException(
                    schedule=schedule,
                    date=exception['date'],
                    type=exception['type'],
                    note=exception.get('note')
                ) for exception in exceptions
            ])
        
        return schedule  #return created schedule instance

    @transaction.atomic
    def update(self, instance, validated_data):
        #Extract exceptions list (if provided)
        exceptions = validated_data.pop('exceptions', None)

        # Delete and recreate exceptions if new ones were provided
        if exceptions is not None:
            #Delete existing exceptions items and recreate
            instance.exceptions.all().delete()

            #Recreate items from the data passed
            DoctorScheduleException.objects.bulk_create(
              [
                DoctorScheduleException(
                    schedule=instance,
                    date=exception['date'],
                    type=exception['type'],
                    note=exception.get('note')
                )
                 for exception in exceptions
              ]
            )

        #update remaining fields
        for field, value in validated_data.items():
            setattr(instance, field, value)  #i.e. instance.field = value

        instance.save(update_fields=list(validated_data.keys()))
        return instance



#Serializer for serving choices for creating and filtering schedules
@doctor_schedules_options_schema
class DoctorScheduleOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    doctorChoices = serializers.SerializerMethodField()
    weekDaysChoices = serializers.SerializerMethodField()
    exceptionTypeChoices = serializers.SerializerMethodField()

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

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_weekDaysChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in WorkingDaysLookUp
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_exceptionTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in DoctorScheduleException.ExceptionTypeChoices
        ]


    # # For translated labels:
    #   from django.utils import translation
    #   def get_weekDaysChoices(self, obj):
    #       result = []
    #       for choice in WorkingDaysLookUp:
    #           with translation.override('en'):
    #               english_label = str(choice.label)
    #           with translation.override('ar'):
    #               arabic_label = str(choice.label)
    #           result.append({
    #               'value': choice.value,
    #               'label': english_label,
    #               'label_ar': arabic_label
    #           })
    #       return result
    
    