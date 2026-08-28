from patients.models import Patient
from rest_framework import serializers
from patients.utils import TEETH_CHOICES
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from clinic.models import Branch, Procedure, Lab, LabOrder
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from services.translation.serializers import TranslatedChoiceField
from clinic.docs import update_lab_order_schema, labs_options_schema


#SERIALIZERS FOR LABS 
#Base labs serializer
class LabSerializer(UserPermissionsMixin, ValidateBranchMixin, serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)

    class Meta:
        model = Lab
        fields = ['id', 'name', 'phone', 'address', 'contactPerson', 'turnaroundDays', 'notes', 'branchId']
        read_only_fields = ['id']


#Retrieve/Update lab serializer
class UpdateLabSerializer(LabSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    
    class Meta(LabSerializer.Meta):
        fields = ['id', 'name', 'phone', 'address', 'contactPerson', 'turnaroundDays', 'notes', 'branchId']
        read_only_fields = ['id', 'branchId']
        extra_kwargs = {field: {'required': False} for field in
            ('name', 'phone', 'address', 'contactPerson', 'turnaroundDays', 'notes')
        }


##########################


#SERIALIZERS FOR LAB ORDERS 
#Lab orders serializer -- base serializer
class LabOrderSerializer(serializers.ModelSerializer):
    labId = serializers.PrimaryKeyRelatedField(source='lab', queryset=Lab.objects.all())
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())
    procedureId = serializers.PrimaryKeyRelatedField(source='procedure', queryset=Procedure.objects.all())
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    status = TranslatedChoiceField(choices=LabOrder.OrderStatusChoices.choices, 
                              required=False, allow_blank=True, allow_null=True)  #not required on create & update

    class Meta:
        model = LabOrder
        fields = ['id', 'labId', 'labName', 'patientId', 'patientName', 'procedureId', 'procedureName', 'toothNumber', 
                  'instructions', 'sentDate', 'dueDate', 'receivedDate', 'deliveredDate', 'status', 'cost', 'currency',
                  'branchId', 'createdAt', 'updatedAt']


#Create lab order serializer
class CreateLabOrderSerializer(ValidateBranchMixin, LabOrderSerializer):
    class Meta(LabOrderSerializer.Meta):
        fields = ['id', 'labId', 'labName', 'patientId', 'patientName', 'procedureId', 'procedureName', 'toothNumber', 
                  'instructions', 'sentDate', 'dueDate', 'receivedDate', 'deliveredDate', 'status', 'cost', 'currency',
                  'branchId', 'createdAt']
        read_only_fields = ['id', 'labName', 'patientName', 'procedureName', 'receivedDate', 'deliveredDate', 'createdAt']


#Update lab order serializer
@update_lab_order_schema
class UpdateLabOrderSerializer(LabOrderSerializer):
    labId = serializers.PrimaryKeyRelatedField(source='lab', queryset=Lab.objects.all(), required=False, allow_null=False)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all(), required=False, allow_null=False)
    procedureId = serializers.PrimaryKeyRelatedField(source='procedure', queryset=Procedure.objects.all(), required=False, allow_null=False)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    status = TranslatedChoiceField(choices=LabOrder.OrderStatusChoices.choices, 
                              required=False, allow_blank=False, allow_null=False)  #not required on create & update

    class Meta(LabOrderSerializer.Meta):
        fields = ['id', 'labId', 'labName', 'patientId', 'patientName', 'procedureId', 'procedureName', 'toothNumber', 
                  'instructions', 'sentDate', 'dueDate', 'receivedDate', 'deliveredDate', 'status', 'cost', 'currency',
                  'branchId', 'updatedAt']
        read_only_fields = ['id', 'labName', 'patientName', 'procedureName', 'sentDate', 'branchId', 'updatedAt']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # order = self.context.get('order', None)   #passed over from view
        order_status = getattr(self.instance, 'status', None)
    
        #Allow editing if status is still pre-production (i.e., 'sent')
        if order_status and order_status != LabOrder.OrderStatusChoices.SENT:
            self.fields['labId'].read_only = True
            self.fields['patientId'].read_only = True
            self.fields['procedureId'].read_only = True
            self.fields['toothNumber'].read_only = True
    

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

