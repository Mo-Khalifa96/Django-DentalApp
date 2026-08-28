from users.models import User
from django.http import Http404
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from utils.mixins import ValidateBranchMixin
from clinic.models import Branch, WaitingRoom
from patients.models import Patient, Appointment
from clinic.docs import waiting_room_options_schema
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField


#Waiting room serializer -- Base serializer
class WaitingRoomSerializer(ValidateBranchMixin, serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all(), required=False, allow_null=True)
    patientName = serializers.SerializerMethodField()
    doctorId = serializers.UUIDField(required=False, allow_null=True)  #read/write
    doctorName = serializers.SerializerMethodField()
    appointmentId = serializers.PrimaryKeyRelatedField(source='appointment', queryset=Appointment.objects.all(), required=False, allow_null=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    status = TranslatedChoiceField(choices=WaitingRoom.StatusChoices.choices, read_only=True)

    class Meta:
        model = WaitingRoom
        fields = ['id', 'patientId', 'patientName', 'doctorId', 'doctorName', 'appointmentId',
                  'branchId', 'room', 'isWalkIn', 'status', 'arrivedAt', 'startedAt', 'completedAt', 'notes']
        read_only_fields = ['id', 'patientName', 'doctorName', 'status', 'arrivedAt',
                            'startedAt', 'completedAt']

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     branch = None
    #     if self.instance:
    #         branch = self.instance.branch
    #     elif self.initial_data:
    #         branch_id = self.initial_data.get('branchId')
    #         if branch_id:
    #             branch = Branch.objects.only('rooms').filter(id=branch_id).first()
    #     if branch and branch.rooms:
    #         self.fields['room'].choices = [(r, r) for r in branch.rooms]

    @extend_schema_field(serializers.UUIDField)
    def get_patientId(self, obj):
        if obj.appointment:
            return obj.appointment.patient_id
        return getattr(obj.patient, 'id', None)

    @extend_schema_field(serializers.CharField)
    def get_patientName(self, obj):
        if obj.appointment:
            return obj.appointment.patient.name
        return getattr(obj.patient, 'name', None)

    @extend_schema_field(serializers.CharField)
    def get_doctorName(self, obj):
        if obj.appointment and obj.appointment.doctor:
            return obj.appointment.doctor.name
        return obj.doctorName or None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        #for output, assign the appointment's doctor id
        if instance.appointment:
            rep['doctorId'] = instance.appointment.doctor_id
        else:
            rep['doctorId'] = instance.doctorId or None
        return rep

    def validate(self, data):
        appointment = data.get('appointment')
        patient = data.get('patient')
        doctor_id = data.pop('doctorId', None)
        doctor = None

        #prepare errors dict
        errors = {}

        #Either patient or appointment is required
        if not appointment and not patient:
            errors['non_field_errors'] = [_('Either a patient ID or an appointment ID is required.')]

        #Validate whether the patient has an appointment or is a walk-in
        if data.get('isWalkIn') == False and not appointment:
            errors['appointmentId'] = _('An appointment is required if a patient is not registered as a walk-in patient. Either assign an appointment or change walk-in status to True.')

        #validate doctor
        if doctor_id:
            try:
                #query to validate and return doctor's id and name
                doctor = User.objects.only('id', 'name').get(id=doctor_id)

                #assign doctor details to snapshot fields
                data['doctorId'] = doctor.id
                data['doctorName'] = doctor.name

            except (User.DoesNotExist, Http404):
                errors['doctorId'] = _('Doctor not found or does not exist.')

        #populate relevant fields (no DB writes yet -- only building up `data` / `errors`)
        if appointment:
            #update walk-in status
            data['isWalkIn'] = False

            #validate patient id if submitted
            if patient and patient.id != appointment.patient_id:
                errors['patientId'] = _('Patient does not match the appointment\'s patient.')

            #assign right patient anyway
            data['patient'] = appointment.patient

        else:
            #update walk-in to True
            data['isWalkIn'] = True

        #raise validation errors (if any) before proceeding
        if errors:
            raise serializers.ValidationError(errors)

        #if current doctor doesn't match appointment doctor, reassign the current one
        if appointment and doctor and doctor.id != appointment.doctor_id:
            appointment.doctor = doctor
            appointment.doctorName = doctor.name
            appointment.save(update_fields=['doctor', 'doctorName', 'updatedAt'])

        return data


#Update waiting room serializer -- for status and room updates
class UpdateWaitingRoomSerializer(serializers.ModelSerializer):
    doctorId = serializers.UUIDField(required=False, allow_null=False)  #read/write
    status = TranslatedChoiceField(choices=WaitingRoom.StatusChoices.choices, required=False, allow_blank=False, allow_null=False)

    class Meta:
        model = WaitingRoom
        fields = ['doctorId', 'status', 'room']
    
    def validate(self, data):
        appointment = getattr(self.instance, 'appointment', None)
        doctor_id = data.pop('doctorId', None)
        doctor = None

        #validate doctor
        if doctor_id:
            try:
                #query to validate and return doctor's id and name
                doctor = User.objects.only('id', 'name').get(id=doctor_id)

                #assign doctor details to snapshot fields
                data['doctorId'] = doctor.id
                data['doctorName'] = doctor.name

            except (User.DoesNotExist, Http404):
                raise serializers.ValidationError(_('Doctor not found or does not exist.'))

        #if current doctor doesn't match appointment doctor, reassign the current one
        if appointment and doctor and doctor.id != appointment.doctor_id:
            appointment.doctor = doctor
            appointment.doctorName = doctor.name
            appointment.save(update_fields=['doctor', 'doctorName', 'updatedAt'])

        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        status = validated_data.get('status')

        if status and status != instance.status:

            if status == WaitingRoom.StatusChoices.IN_CHAIR:
                instance.startedAt = timezone.localtime(timezone.now())

            elif status == WaitingRoom.StatusChoices.DONE:
                #set completedAt to now
                completedAt = timezone.localtime(timezone.now())
                #update completedAt
                instance.completedAt = completedAt

                #also update appointment-related details (if not a walk-in)
                if instance.appointment:
                    instance.appointment.status = 'completed'
                    instance.appointment.endTime = completedAt
                    instance.appointment.save(update_fields=['status', 'endTime', 'updatedAt'])

                    #set patient's next appointment to null
                    instance.appointment.patient.nextAppointment = None 
                    instance.appointment.patient.save(update_fields=['nextAppointment', 'updatedAt'])

        #call parent update() method
        return super().update(instance, validated_data)


@waiting_room_options_schema
class WaitingRoomOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    doctorChoices = serializers.SerializerMethodField()
    statusChoices = serializers.SerializerMethodField()
    roomChoices = serializers.SerializerMethodField()

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
        if not branchId and Branch.objects.exists():
            return []
        
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
    def get_statusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in WaitingRoom.StatusChoices
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
