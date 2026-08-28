from users.models import User
from django.db import transaction
from rest_framework import serializers
from clinic.models import Branch, Procedure
from utils.mixins import UserPermissionsMixin
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from patients.models import Patient, Appointment, Visit
from patients.serializers.patients import NewPatientSerializer
from services.translation.serializers import TranslatedChoiceField
from patients.docs import appointments_options_schema, cancel_appointment_schema


#APPOINTMENTS SERIALIZERS 
#List / Base appointments serializer 
class AppointmentSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())  #read/write
    patientName = serializers.CharField(source='patient.name', read_only=True)
    doctorId = serializers.PrimaryKeyRelatedField(source='doctor', queryset=User.objects.filter(role__in=['admin', 'dentist', 'assistant']))
    procedureId = serializers.PrimaryKeyRelatedField(source='procedure', queryset=Procedure.objects.all())
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    status = TranslatedChoiceField(choices=Appointment.AppointmentStatusChoices.choices, required=False, allow_blank=True, allow_null=True)
    type = TranslatedChoiceField(choices=Visit.VisitTypeChoices.choices)

    class Meta:
        model = Appointment
        fields = ['id', 'patientId', 'patientName', 'doctorId', 'doctorName', 'procedureId', 'type',
                  'date', 'startTime', 'endTime', 'room', 'status', 'notes', 'branchId', 'createdAt', 
                  'updatedAt']


#Retrieve appointments serializer (inherits from appointment serializer)
class RetrieveAppointmentSerializer(UserPermissionsMixin, AppointmentSerializer):
    # patientPhone = serializers.CharField(source='patient.phone', read_only=True)
    patientPhone = serializers.SerializerMethodField()

    class Meta(AppointmentSerializer.Meta):
        fields = ['id', 'patientId', 'patientName', 'patientPhone', 'doctorId', 'doctorName', 'procedureId', 
                  'type', 'date', 'startTime', 'endTime', 'room', 'status', 'notes', 'branchId', 'createdAt', 'updatedAt']

    @extend_schema_field(serializers.CharField)
    def get_patientPhone(self, obj):
        return '0' + obj.patient.phone[len(obj.patient.countryCode):]


#Create appointment serializer (inherits from appointment serializer)
class CreateAppointmentSerializer(AppointmentSerializer):
    #override patientId field to make it optional
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all(), 
                                                   required=False, allow_null=True)
    #new fields for creating new patients
    is_newPatient = serializers.BooleanField(default=False, required=False, write_only=True)
    newPatientDetails = NewPatientSerializer(many=False, allow_null=True, required=False, write_only=True)

    class Meta(AppointmentSerializer.Meta):
        fields = ['id', 'patientId', 'patientName', 'is_newPatient', 'newPatientDetails', 'doctorId', 
                  'doctorName', 'procedureId', 'type', 'date', 'startTime', 'endTime', 'room', 'status', 
                  'notes', 'branchId', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'patientName', 'doctorName', 'status', 'createdAt', 'updatedAt']

    #validate patient-related data
    def validate(self, data):
        is_new = data.get('is_newPatient', False)
        patient = data.get('patient') #patientId accessed as simply patient given source param
        new_patient_details = data.get('newPatientDetails')
        branch = data.get('branch')
        doctor = data.get('doctor')
    
        #Validate patient-related data
        if is_new:
            if not new_patient_details:
                raise serializers.ValidationError({'newPatientDetails': _('Patient details are required if creating a new patient.')})            
            if patient:
                raise serializers.ValidationError({'patientId': _('Cannot assign an existing patient if choosing to create a new one.')})
        else:
            if not patient:
                if new_patient_details:
                    data['is_newPatient'] = True
                else:
                    raise serializers.ValidationError({'patientId': _('Existing patient ID or new patient details are required.')})

        #validate branch
        if not branch:
            user = self.context['request'].user
            if user.branches.count() == 1:
                branch = user.branches.first()
                data['branch'] = branch
            elif getattr(user, 'branch_id', None):
                branch = user.branch
                data['branch'] = branch
            elif doctor and doctor.branches.count() == 1:
                branch = doctor.branches.first()
                data['branch'] = branch
            elif doctor and getattr(doctor, 'branch_id', None):
                branch = doctor.branch
                data['branch'] = branch
            elif Branch.objects.exists():
                raise serializers.ValidationError(_('Clinic branch must be provided when at least one branch is registered. Please provide a branch ID or contact the admin to assign a branch to your account.'))

        #validate appointment availability
        Appointment.validate_availability(
            doctorId=data.get('doctor'),
            branchId=getattr(branch, 'id', None),
            date=data.get('date'),
            startTime=data.get('startTime'),
            endTime=data.get('endTime')
        )
        
        return data

    @transaction.atomic 
    def create(self, validated_data):
        is_new = validated_data.pop('is_newPatient', False)
        newPatientDetails = validated_data.pop('newPatientDetails', None)
        
        #Create new patient (if provided) and assign to patient field (patientId maps to 'patient' anyway)
        if is_new and newPatientDetails:
            patient = Patient.objects.create(**newPatientDetails, 
                                             doctor=validated_data['doctor'],
                                             branch=validated_data.get('branch'))
            
            #add patient object to validated data
            validated_data['patient'] = patient

        else:
            patient = validated_data.get('patient')
            patient.doctor = validated_data['doctor']
            patient.branch = validated_data.get('branch')
            patient.save(update_fields=['branch', 'doctor', 'doctorName', 'updatedAt'])
        
        #Call parent create method to create appointment with updated data
        return super().create(validated_data)


#Update appointment serializer
class UpdateAppointmentSerializer(AppointmentSerializer):
    doctorId = serializers.PrimaryKeyRelatedField(source='doctor', 
                queryset=User.objects.filter(role__in=['admin', 'dentist', 'assistant']), 
                required=False)
    status = TranslatedChoiceField(choices=Appointment.AppointmentStatusChoices.choices, required=False, allow_blank=False, allow_null=False)
    procedureId = serializers.PrimaryKeyRelatedField(source='procedure', queryset=Procedure.objects.all(), required=False)
    type = TranslatedChoiceField(choices=Visit.VisitTypeChoices.choices, required=False)

    class Meta(AppointmentSerializer.Meta):
        fields = ['id', 'doctorId', 'procedureId', 'type', 'date', 'startTime', 'endTime', 
                  'room', 'status', 'notes', 'branchId', 'updatedAt']
        read_only_fields = ['id', 'updatedAt']
        extra_kwargs = {field: {'required': False} for field in 
            ('procedureId', 'type', 'date', 'startTime', 'endTime', 'room', 'status', 'notes', 'branchId')
         }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # order = self.context.get('appointment', None)   #passed over from view
        status = getattr(self.instance, 'status', None)
    
        #Allow editing if status is still pending or confirmed
        if status and status in (Appointment.AppointmentStatusChoices.PENDING, Appointment.AppointmentStatusChoices.CONFIRMED):
            self.fields['procedureId'].read_only = True
            self.fields['type'].read_only = True    

    #validate patient-related data 
    def validate(self, data):
        instance = self.instance
        doctor = data.get('doctor', instance.doctor) or instance.doctor
        branch = data.get('branch', instance.branch) or instance.branch
        
        #validate branch
        if not branch:
            user = self.context['request'].user
            if user.branches.count() == 1:
                branch = user.branches.first()
                data['branch'] = branch
            elif doctor and doctor.branches.count() == 1:
                branch = instance.doctor.branches.first()
                data['branch'] = branch
            elif getattr(user, 'branch_id', None):
                branch = user.branch
                data['branch'] = branch
            elif doctor and getattr(doctor, 'branch_id', None):
                branch = doctor.branch
                data['branch'] = branch
            elif Branch.objects.exists():
                raise serializers.ValidationError(_('Clinic branch must be provided when at least one branch is registered. Please provide a branch ID or contact the admin to assign a branch to your account.'))

        #validate appointment availability
        Appointment.validate_availability(
            doctorId=doctor.id,
            branchId=getattr(branch, 'id', None),
            date=data.get('date', instance.date),
            startTime=data.get('startTime', instance.startTime),
            endTime=data.get('endTime', instance.endTime),
            current_id=instance.id
        )

        return data 


#Cancel appointment serializer
@cancel_appointment_schema
class CancelAppointmentSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)  


#Serializer for serving choice options for appointment creation
@appointments_options_schema
class AppointmentOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    doctorChoices = serializers.SerializerMethodField()
    typeChoices = serializers.SerializerMethodField()
    statusChoices = serializers.SerializerMethodField()
    roomChoices = serializers.SerializerMethodField()

    #Get branches choices (with name and id)
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

    #Get patients choices (with id and name)
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_patientChoices(self, obj):
        branchId = self.context.get('branchId')
        doctorId = self.context.get('doctorId') 
        
        if (not branchId and Branch.objects.exists()) and not doctorId:
            return []
        
        filters = {}
        if branchId:
            filters['branch_id'] = branchId
        if doctorId:
            filters['doctor_id'] = doctorId
        
        return [
            {'patientId': patient_id, 'name': name}
             for patient_id, name in Patient.objects.filter(**filters)\
              .values_list('id', 'name').order_by('name')
        ]

    #Get doctors list (with id and name)
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_doctorChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId, 'role__in': ['dentist', 'admin']} if branchId else {'role__in': ['dentist', 'admin']}
        return [
            {'doctorId': doctor_id, 'name': name}
             for doctor_id,name in User.objects.only('id','name','role', 'branch')\
              .filter(**filters).values_list('id', 'name').order_by('name')
        ]

    #Get appointment type choices
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_typeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Visit.VisitTypeChoices
        ]

    #Get status choices
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_statusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Appointment.AppointmentStatusChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_roomChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId:
            return []
        
        branch = Branch.objects.get(id=branchId)
        return [
            {'value': room, 'label': room}
                for room in branch.rooms
        ]
