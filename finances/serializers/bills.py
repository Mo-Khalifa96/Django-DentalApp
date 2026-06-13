import logging
from decimal import Decimal
from clinic.models import Branch
from django.db import transaction
from rest_framework import serializers
from finances.models import Bill, Invoice
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from patients.models import Patient, TreatmentPlan, Visit
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from finances.docs import list_bills_schema, retrieve_bills_schema, bills_options_schema


#Initiate logger 
logger = logging.getLogger(__name__)

#BILLS SERIALIZERS 

#Bill status labels
STATUS_LABELS = {
    'unpaid': _('unpaid'),
    'partial': _('partial'),
    'paid': _('paid'),
}

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
                  'procedures', 'branchId', 'branchName', 'description', 'discount', 'subtotal', 
                  'total', 'currency', 'status', 'createdBy', 'createdAt', 'updatedAt', 'isDeleted']


    @extend_schema_field(serializers.CharField)
    def get_status(self, obj):
        value = getattr(obj, 'status', None)
        return str(STATUS_LABELS.get(value, value)) if value else None
    

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


#Create bill serializer
class CreateBillSerializer(serializers.ModelSerializer, ValidateBranchMixin):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all(), required=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='treatment', queryset=TreatmentPlan.objects.all(), required=False, allow_null=True)
    visitIds = serializers.PrimaryKeyRelatedField(many=True, source='visits', queryset=Visit.objects.all(), required=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)
    total = serializers.DecimalField(source='totalAmount', max_digits=10, decimal_places=2, required=False)

    class Meta:
        model = Bill
        fields = ['id', 'patientId', 'patientName', 'treatmentId', 'visitIds', 'branchId', 
                  'description', 'discount', 'subtotal', 'total', 'currency', 'createdAt']
        read_only_fields = ['id', 'patientName', 'createdAt']
    

    def validate(self, data):
        #get request user 
        user = self.context.get('request').user
        
        #extract fields for validation
        patient = data.get('patient')
        treatment = data.get('treatment')
        visits = data.get('visits', [])
        subtotal = data.get('subtotal')
        discount = data.get('discount', Decimal('0'))
        totalAmount = data.get('totalAmount', None)

        #assign user's name to 'createdBy' field
        data['createdBy'] = user.name

        #perpare errors dict
        errors = {}

        #validate treatment 
        if treatment:
            #treatment must belong to the same patient
            if treatment.patient_id != patient.id:
                errors['treatmentId'] = []
                errors.setdefault('treatmentId', []).append(
                    _('Treatment plan does not belong to this patient.')
                )
            
            #bill's total amount cannot be higher than treatment cost
            if treatment.totalCost and treatment.installmentMonths == 1\
                and round(subtotal,2) > round(treatment.totalCost,2):
                errors['treatmentId'] = errors.get('treatmentId', [])
                errors.setdefault('treatmentId', []).append(
                    _('Total amount cannot be higher than treatment plan cost if a treatment plan with no installments is assigned.')
                )

        #validate all visits belong to the same patient
        if any([visit for visit in visits if visit.patient_id != patient.id]):
            errors['visitIds'] = _('One or more visits do not belong to this patient.')


        #validate amount fields
        if discount > subtotal:
            errors['discount'] = _('Discount cannot exceed subtotal amount.')

        #handle total amount calculation
        recalculated_total = subtotal - discount
        if totalAmount and (
         round(totalAmount,2) != round(recalculated_total,2)
         or abs(totalAmount - recalculated_total) > 0.01):
            logger.error(f'\nFRONTEND BUG: Bill total amount miscalculated. '
             f'Provided: {totalAmount}, Actual: {recalculated_total}\n')
        #assign recalculated total anyway
        data['totalAmount'] = recalculated_total

        #return val errors (if any)
        if errors:
            raise serializers.ValidationError(errors)

        return data


    @transaction.atomic
    def create(self, validated_data):
        #Handle visits manually given M2M relation
        visits = validated_data.pop('visits', [])

        #create bill instance first
        bill = Bill.objects.create(**validated_data)

        #set visits to instance
        if visits:
            bill.visits.set(visits)
        
        #return created instance
        return bill


#Update bill serializer
class UpdateBillSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='treatment', queryset=TreatmentPlan.objects.all(), required=False, allow_null=True)
    visitIds = serializers.PrimaryKeyRelatedField(many=True, source='visits', queryset=Visit.objects.all(), required=False, allow_empty=False)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, source='totalAmount', required=False)

    class Meta:
        model = Bill
        fields = ['id', 'patientId', 'patientName', 'treatmentId', 'visitIds', 'branchId', 
                  'description', 'discount', 'subtotal', 'total', 'currency', 'updatedAt']
        read_only_fields = ['id', 'patientId', 'patientName', 'branchId', 'updatedAt']
        extra_kwargs = {field: {'required': False} for field in 
            ('description', 'discount', 'subtotal', 'total', 'currency')
            }

    def validate(self, data):
        #extract fields for validation
        visits = data.get('visits', [])
        treatment = data.get('treatment', None)
        subtotal = data.get('subtotal', self.instance.subtotal)
        discount = data.get('discount', self.instance.discount)
        totalAmount = data.get('totalAmount', self.instance.totalAmount)

        #validate visits are not removed  -- TODO: confirm with frontend
        # if 'visits' in data:
        #     incoming_visit_ids = {visit.id for visit in visits}
        #     existing_visit_ids = set(self.instance.visits.values_list('id', flat=True))
        #     removed = existing_visit_ids - incoming_visit_ids
        #     if removed:
        #         raise serializers.ValidationError({
        #             'visitIds': _('Existing visits cannot be removed from a bill. Only adding new visits is permitted.')
        #         })

        #prepare errors dict
        errors = {}

        #validate treatment 
        if 'treatment' in data and treatment:
            #treatment must belong to the same patient
            if treatment.patient_id != self.instance.patient_id:
                errors.setdefault('treatmentId', []).append(
                    _('Treatment plan does not belong to this patient.')
                )
            #bill's total amount cannot be higher than treatment cost
            if treatment.totalCost and treatment.installmentMonths == 1\
                and round(subtotal,2) > round(treatment.totalCost,2):
                errors.setdefault('treatmentId', []).append(
                    _('Total amount cannot be higher than treatment plan cost if a treatment plan with no installments is assigned.')
                )

        #validate all visits belong to the same patient
        if 'visits' in data and any([visit for visit in visits if visit.patient_id != self.instance.patient_id]):
            errors['visitIds'] = _('One or more visits do not belong to this patient.')

        #validate amount fields
        if discount > subtotal:
            errors['discount'] = _('Discount cannot exceed subtotal amount.')

        #handle total amount calculation
        recalculated_total = subtotal - discount
        if 'totalAmount' in data and (
         round(totalAmount,2) != round(recalculated_total,2)
         or abs(totalAmount - recalculated_total) > 0.01):
            logger.error(f'\nFRONTEND BUG: Bill total amount miscalculated. '
             f'Provided: {totalAmount}, Actual: {recalculated_total}\n')
        #assign recalculated total anyway
        data['totalAmount'] = recalculated_total

        #return val errors (if any)
        if errors:
            raise serializers.ValidationError(errors)

        return data

    
    @transaction.atomic
    def update(self, instance, validated_data): 
        #Handle visits manually given M2M relation
        visits = validated_data.pop('visits', None)

        #update fields with new values
        update_fields = []
        for field, value in validated_data.items():
            setattr(instance, field, value)
            update_fields.append(field)
        instance.save(update_fields=[*update_fields, 'updatedAt'])

        #add new visits only -- TODO: to be confirmed
        # instance.visits.add(*visits)

        #update visits if provided
        if visits is not None:
            #replace existing relations (will also trigger signal)
            instance.visits.set(visits)

        #return updated instance
        return instance


#Autogenerate invoice serializer
class AutogenerateInvoiceSerializer(serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    patientName = serializers.CharField(source='patient.name', read_only=True)
    patientNationalId = serializers.CharField(source='patient.nationalId', read_only=True)
    billId = serializers.PrimaryKeyRelatedField(source='bill', queryset=Bill.objects.all(), required=True)
    # items = InvoiceItemsSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'invoiceNumber', 'patientId', 'patientName', 'patientNationalId', 'billId', 
                # 'invoice_items', 
                'subtotal', 'discount', 'total', 'currency', 'status', 'issuedAt', 'branchId']
        read_only_fields = ['id', 'invoiceNumber', 'patientId', 'patientName', 'patientNationalId',
            # 'invoice_items', 
            'subtotal', 'discount', 'total', 'currency', 'status', 'issuedAt', 'branchId']

    @transaction.atomic
    def create(self, validated_data):
        #get bill instance
        bill = validated_data.get('bill')

        #generate invoice from bill
        invoice = Bill.generate_invoice(bill=bill)
         
        #return invoice
        return invoice


#Bills options serializer
@bills_options_schema
class BillsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    patientTreatmentChoices = serializers.SerializerMethodField()
    patientVisitChoices = serializers.SerializerMethodField()

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
        
        # if (not branchId and Branch.objects.exists()) and not doctorId:
        #     return []
        
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
    def get_patientTreatmentChoices(self, obj):
        patientId = self.context.get('patientId')
        patient_filter = {'patient_id': patientId} if patientId else {}

        return [
            {'treatmentId': treatment_id} 
            for treatment_id in TreatmentPlan.objects.filter(**patient_filter)\
             .values_list('id', flat=True)
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_patientVisitChoices(self, obj):
        patientId = self.context.get('patientId')
        patient_filter = {'patient_id': patientId} if patientId else {}

        return [
            {'visitId': visit_id} 
            for visit_id in Visit.objects.filter(**patient_filter)\
             .values_list('id', flat=True)
        ]


