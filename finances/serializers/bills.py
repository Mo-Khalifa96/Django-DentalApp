import logging
from decimal import Decimal
from clinic.models import Branch
from finances.models import Bill
from django.db import transaction 
from rest_framework import serializers
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from patients.models import Patient, TreatmentPlan, Visit
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from finances.docs import list_bills_schema, retrieve_bills_schema


#Initiate logger 
logger = logging.getLogger(__name__)

#BILLS SERIALIZERS 
#Bills serializer
@list_bills_schema
class BillSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='treatment', read_only=True)
    visitIds = serializers.PrimaryKeyRelatedField(many=True, source='visits', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, source='totalAmount', read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = ['id', 'patientId', 'patientName', 'treatmentId', 'treatmentTitle', 'visitIds', 
                  'procedures', 'branchId', 'branchName', 'description', 'currency', 'discount', 
                  'subtotal', 'total', 'status', 'createdBy', 'createdAt', 'updatedAt', 'isDeleted']
    

    @extend_schema_field(serializers.CharField)
    def get_status(self, obj):
        total_paid = obj.totalPaid or Decimal('0')
        total_amount = obj.totalAmount or Decimal('0')
        
        if total_paid == 0:
            return 'unpaid'
        elif total_amount > total_paid:
            return 'partial'
        elif total_amount <= total_paid:
            return 'paid'
        
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        #Remove snapshot fields for non-admins
        if request and getattr(request.user, 'role', None) != 'admin':
            fields.pop('treatmentTitle', None)
            fields.pop('procedures', None)
            fields.pop('branchName', None)
            fields.pop('createdBy', None)
            fields.pop('isDeleted', None)
        return fields
    

#Retrieve bill details serializer
@retrieve_bills_schema
class RetrieveBillSerializer(UserPermissionsMixin, BillSerializer):
    pass


#Base bill serializer for create/update
class CreateUpdateBillSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())
    treatmentId = serializers.PrimaryKeyRelatedField(source='treatment', queryset=TreatmentPlan.objects.all())
    visitIds = serializers.PrimaryKeyRelatedField(many=True, source='visits', queryset=Visit.objects.all())
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, source='totalAmount', required=False)

    class Meta:
        model = Bill
        fields = ['id', 'patientId', 'patientName', 'treatmentId', 'visitIds', 'branchId', 
                  'description', 'currency', 'discount', 'subtotal', 'total', 'createdAt']
        read_only_fields = ['id', 'patientName', 'createdAt']
    
    def validate(self, data):
        #get request user 
        user = self.context.get('request').user
        #assign user's name to 'createdBy' field
        data['createdBy'] = user.name

        #extract amount fields for validation
        subtotal = data['subtotal']
        totalAmount = data.get('totalAmount')
        discount = data.get('discount')


        return data

        #validate amount fields
        # discount = discount or Decimal('0')
        # if totalAmount:
        #     if discount:
        #         recalculated_total = subtotal - discount
        #         if totalAmount and recalculated_total != totalAmount:
        #             logger.error(f'\n\nFRONTEND BUG: Total amount provided is miscalculated. Total provided: {totalAmount}. Actual total: {recalculated_total}')
        #             totalAmount = recalculated_total
        #     else:
        #         if subtotal != totalAmount:
        #             raise serializers.ValidationError({'subtotal': _('Total amount miscalculation: total and subtotal amounts must be equal when discount is not applied.')})


    @transaction.atomic
    def create(self, validated_data):
        pass
    
    @transaction.atomic
    def update(self, instance, validated_data): 
        pass



#Create bill serializer 
class CreateBillSerializer(CreateUpdateBillSerializer, ValidateBranchMixin):
    pass


#Update bill serializer
class UpdateBillSerializer(CreateUpdateBillSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='treatment', read_only=True)
    visitIds = serializers.PrimaryKeyRelatedField(many=True, source='visits', queryset=Visit.objects.all())
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, source='totalAmount', required=False)

    class Meta(CreateUpdateBillSerializer.Meta):
        fields = ['id', 'patientId', 'patientName', 'treatmentId', 'visitIds', 'branchId', 
                  'description', 'discount', 'subtotal', 'total', 'currency', 'updatedAt']
        read_only_fields = ['id', 'patientId', 'patientName', 'treatmentId', 'branchId', 'updatedAt']
