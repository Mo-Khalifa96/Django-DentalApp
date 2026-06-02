from users.models import User
from rest_framework import serializers
from patients.models import Appointment
from clinic.models import Branch, WaitingRoom
from utils.mixins import ValidateBranchMixin
from clinic.docs import waiting_room_options_schema
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _


#Waiting room serializer -- Base serializer
class WaitingRoomSerializer(serializers.ModelSerializer, ValidateBranchMixin):
    patientId = serializers.PrimaryKeyRelatedField(source='appointment.patient', read_only=True)
    patientName = serializers.CharField(source='appointment.patient.name', read_only=True)
    doctorId = serializers.UUIDField(required=False, allow_null=True)  #read/write
    doctorName = serializers.CharField(source='appointment.doctor.name', read_only=True)
    appointmentId = serializers.PrimaryKeyRelatedField(source='appointment', queryset=Appointment.objects.all(), required=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = WaitingRoom
        fields = ['id', 'patientId', 'patientName', 'doctorId', 'doctorName', 'appointmentId',
                  'branchId', 'room', 'status', 'arrivedAt', 'startedAt', 'completedAt']
        read_only_fields = ['id', 'patientId', 'patientName', 'doctorName', 'status', 'arrivedAt',
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


    def to_representation(self, instance):
        rep = super().to_representation(instance)
        #for output, assign the appointment's doctor id
        rep['doctorId'] = instance.appointment.doctor_id
        return rep

    def validate(self, data):
        doctor_id = data.pop('doctorId', None)
        appointment = data.get('appointment')

        if doctor_id:
            try:
                #query to validate and return doctor's id and name
                doctor = User.objects.only('id', 'name').get(id=doctor_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({'doctorId': _('Doctor not found or does not exist.')})

        #if current doctor doesn't match appointment doctor
        if doctor and doctor.id != appointment.doctor_id:
            #assign current doctor by id
            appointment.doctor = doctor
            appointment.doctorName = doctor.name
            appointment.save(update_fields=['doctor', 'doctorName', 'updatedAt'])

        return data
    

#Update waiting room serializer -- for status and room updates
class UpdateWaitingRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaitingRoom
        fields = ['status', 'room']


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
