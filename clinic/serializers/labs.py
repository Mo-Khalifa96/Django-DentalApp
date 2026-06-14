from patients.models import Patient
from rest_framework import serializers
from patients.utils import TEETH_CHOICES
from clinic.docs import labs_options_schema
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from clinic.models import Branch, Procedure, Lab, LabOrder
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from services.translation.serializers import TranslatedChoiceField


#SERIALIZERS FOR LABS 
#Base labs serializer
class LabSerializer(UserPermissionsMixin, serializers.ModelSerializer, ValidateBranchMixin):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Lab
        fields = ['id', 'name', 'phone', 'address', 'contactPerson', 'notes', 'branchId']
        read_only_fields = ['id']


#Retrieve/Update lab serializer
class RetrieveUpdateLabSerializer(LabSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    
    class Meta(LabSerializer.Meta):
        fields = ['id', 'name', 'phone', 'address', 'contactPerson', 'notes', 'branchId']
        read_only_fields = ['id', 'branchId']
        extra_kwargs = {field: {'required': False} for field in
            ('name', 'phone', 'address', 'contactPerson', 'notes')
        }


##########################


#SERIALIZERS FOR LAB ORDERS 
#Lab orders serializer -- base serializer
class LabOrderSerializer(serializers.ModelSerializer):
    labId = serializers.PrimaryKeyRelatedField(source='lab', queryset=Lab.objects.all())
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())
    procedureId = serializers.PrimaryKeyRelatedField(source='procedure', queryset=Procedure.objects.all())
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)
    status = TranslatedChoiceField(choices=LabOrder.OrderStatusChoices.choices, allow_blank=True, allow_null=True)

    class Meta:
        model = LabOrder
        fields = ['id', 'labId', 'labName', 'patientId', 'patientName', 'procedureId', 'procedureName', 'toothNumber', 
                  'instructions', 'sentDate', 'dueDate', 'receivedDate', 'deliveredDate', 'status', 'cost', 'currency',
                  'branchId', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'labName', 'patientName', 'procedureName', 'receivedDate', 'deliveredDate', 
                            'createdAt', 'updatedAt']


#Create lab order serializer
class CreateLabOrderSerializer(LabOrderSerializer, ValidateBranchMixin):
    class Meta(LabOrderSerializer.Meta):
        fields = ['id', 'labId', 'labName', 'patientId', 'patientName', 'procedureId', 'procedureName', 'toothNumber', 
                  'instructions', 'sentDate', 'dueDate', 'receivedDate', 'deliveredDate', 'status', 'cost', 'currency',
                  'branchId', 'createdAt']
        read_only_fields = ['id', 'labName', 'patientName', 'procedureName', 'receivedDate', 'deliveredDate', 'createdAt']


#Update lab order serializer
class UpdateLabOrderSerializer(LabOrderSerializer):
    status = TranslatedChoiceField(choices=LabOrder.OrderStatusChoices.choices, 
                             required=False, allow_blank=False, allow_null=False)

    class Meta(LabOrderSerializer.Meta):
        fields = ['id', 'labId', 'labName', 'patientId', 'patientName', 'procedureId', 'procedureName', 'toothNumber', 
                  'instructions', 'sentDate', 'dueDate', 'receivedDate', 'deliveredDate', 'status', 'cost',
                  'branchId', 'updatedAt']
        read_only_fields = ['id', 'labId', 'labName', 'patientId', 'patientName', 'procedureId', 'procedureName', 
                            'toothNumber', 'sentDate', 'currency', 'branchId', 'updatedAt']


#Lab orders options serializer
@labs_options_schema
class LabOrdersOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    labChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    procedureChoices = serializers.SerializerMethodField()
    orderStatus = serializers.SerializerMethodField()
    validToothNumbers = serializers.SerializerMethodField()


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
    def get_labChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId} if branchId else {}
        return [
            {'labId': lab_id, 'name': name}
             for lab_id,name in Lab.objects.filter(**filters)\
              .values_list('id', 'name').order_by('name')
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_patientChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId} if branchId else {}
        return [
            {'patientId': patient_id, 'name': name} 
             for patient_id,name in Patient.objects.filter(**filters)\
              .values_list('id', 'name').order_by('name')
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_procedureChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId} if branchId else {}
        return [
                {'procedureId': procedure_id, 'name': name}
                 for procedure_id,name in Procedure.objects.filter(**filters)\
                  .values_list('id', 'name').order_by('name')
            ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_orderStatus(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in LabOrder.OrderStatusChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_validToothNumbers(self, obj):
        return [
            {'value': tooth[0], 'label': tooth[1]}
             for tooth in TEETH_CHOICES
        ]

