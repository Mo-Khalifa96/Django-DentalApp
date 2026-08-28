from clinic.models import Branch
from django.db import transaction
from rest_framework import serializers
from utils.mixins import ValidateBranchMixin
from patients.models import Patient, PatientRecall
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from patients.docs import patient_recalls_options_schema
from services.translation.serializers import TranslatedChoiceField


#SERIALIZERS FOR PATIENT RECALLS
#Patient recalls serializer -- base serializer
class PatientRecallSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    patientName = serializers.CharField(source='patient.name', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    type = TranslatedChoiceField(choices=PatientRecall.RecallTypeChoices.choices)
    status = TranslatedChoiceField(choices=PatientRecall.RecallStatusChoices.choices,
                                    required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = PatientRecall
        fields = ['id', 'patientId', 'patientName', 'phone', 'type', 'dueDate', 'notes', 
                  'status', 'contactedAt', 'branchId', 'createdAt', 'updatedAt']


#Create patient recall serializer
class CreatePatientRecallSerializer(ValidateBranchMixin, PatientRecallSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)

    class Meta(PatientRecallSerializer.Meta):
        fields = ['id', 'patientId', 'patientName', 'phone', 'type', 'dueDate', 'notes', 
                  'status', 'branchId', 'createdAt']
        read_only_fields = ['id', 'patientName', 'createdAt']
        # validators = []

    @transaction.atomic
    def create(self, validated_data):
        patient = validated_data.pop('patient')
        recall_type = validated_data.pop('type')
        recall_status = validated_data.pop('status', None) or PatientRecall.RecallStatusChoices.PENDING

        if recall_status == PatientRecall.RecallStatusChoices.PENDING\
         and recall_type == PatientRecall.RecallTypeChoices.CHECKUP:
            recall, _ = PatientRecall.objects.update_or_create(
                        patient=patient,
                        type=PatientRecall.RecallTypeChoices.CHECKUP,
                        status='pending',
                        defaults=validated_data
                    )
        else:
            recall = PatientRecall.objects.create(
                        patient=patient,
                        type=recall_type,
                        status=recall_status,
                        **validated_data
                    )
        
        return recall
    

#Update patient recall serializer
class UpdatePatientRecallSerializer(PatientRecallSerializer):
    type = TranslatedChoiceField(choices=PatientRecall.RecallTypeChoices.choices, required=False)
    status = TranslatedChoiceField(choices=PatientRecall.RecallStatusChoices.choices,
                                   required=False, allow_blank=False, allow_null=False)

    class Meta(PatientRecallSerializer.Meta):
        fields = ['id', 'patientId', 'patientName', 'phone', 'type', 'dueDate', 'notes', 
                  'status', 'contactedAt', 'branchId', 'updatedAt']
        read_only_fields = ['id', 'patientId', 'patientName', 'branchId', 'updatedAt']


#Patient recalls options serializer
@patient_recalls_options_schema
class PatientRecallsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    recallTypeChoices = serializers.SerializerMethodField()
    recallStatusChoices = serializers.SerializerMethodField()

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
            {'patientId': patient_id, 'name': name, 'phone': phone}
             for patient_id, name, phone in Patient.objects.filter(**filters)\
              .values_list('id', 'name', 'phone').order_by('name')
        ]
    
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_recallTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in PatientRecall.RecallTypeChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_recallStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in PatientRecall.RecallStatusChoices
        ]

