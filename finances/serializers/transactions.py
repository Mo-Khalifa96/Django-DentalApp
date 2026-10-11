from django.http import Http404
from clinic.models import Branch
from django.db import transaction
from rest_framework import serializers
from finances.models import Bill, Transaction
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from patients.models import Patient, Visit, TreatmentPlan
from utils.mixins import ValidateBranchMixin, UserPermissionsMixin
from services.translation.serializers import TranslatedChoiceField
from finances.docs import list_transactions_schema, retrieve_transaction_schema, transactions_options_schema


#Transactions serializer -- base serializer
@list_transactions_schema
class TransactionSerializer(serializers.ModelSerializer):
    billId = serializers.PrimaryKeyRelatedField(source='bill', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    visitId = serializers.PrimaryKeyRelatedField(source='visit', read_only=True)
    installmentPlanId = serializers.PrimaryKeyRelatedField(source='bill.installmentPlan', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, read_only=True)
    type = TranslatedChoiceField(choices=Transaction.TransactionTypeChoices.choices, read_only=True)
    status = TranslatedChoiceField(choices=Transaction.TransactionStatusChoices.choices, read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'billId', 'billDescription', 'patientId', 'patientName', 'visitId', 'treatmentTitle', 
                  'installmentPlanId', 'branchId', 'branchName', 'date', 'amount', 'currency', 'method', 'type', 
                  'status', 'notes', 'createdBy', 'isDeleted']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        #Remove snapshot fields for non-admins
        if request and getattr(request.user, 'role', None) != 'admin':
            fields.pop('billDescription', None)
            fields.pop('treatmentTitle', None)
            fields.pop('branchName', None)
            fields.pop('createdBy', None)
            fields.pop('isDeleted', None)
        return fields

@retrieve_transaction_schema
class RetrieveTransactionSerializer(UserPermissionsMixin, TransactionSerializer):
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'billId', 'billDescription', 'patientId', 'patientName', 'visitId', 'treatmentTitle', 
            'installmentPlanId', 'branchId', 'branchName', 'date', 'amount', 'currency', 'method', 'type', 
            'status', 'notes', 'refundReason', 'correctionReason', 'createdBy', 'isDeleted']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        #Remove snapshot fields for non-admins
        if request and getattr(request.user, 'role', None) != 'admin':
            fields.pop('billDescription', None)
            fields.pop('treatmentTitle', None)
            fields.pop('branchName', None)
            fields.pop('createdBy', None)
            fields.pop('isDeleted', None)
        return fields



#Create transaction serializer 
class CreateTransactionSerializer(TransactionSerializer):
    billId = serializers.PrimaryKeyRelatedField(source='bill', queryset=Bill.objects.all())
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    visitId = serializers.PrimaryKeyRelatedField(source='visit', queryset=Visit.objects.all(), required=False, allow_null=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, 
                                   required=False, allow_blank=True, allow_null=True)
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'billId', 'patientId', 'patientName', 'visitId', 'branchId', 
                  'date', 'amount', 'currency', 'method', 'type', 'notes']
        read_only_fields = ['id', 'patientId', 'patientName', 'type', 'branchId']

    def validate(self, data):
        #visit = data.get('visit')
        bill = data.get('bill')
        amount = data.get('amount')
        method = data.get('method', 'cash')

        #if insurance payment, validate insurance is still active
        coverage = bill.patient.patient_insurance
        if coverage and method == 'insurance':
            coverage.validate_coverage_for_transaction(transaction_amount=amount)
                    
        #Auto-fill other data
        #get request user
        user = self.context.get('request').user
        
        #assign user's name to 'createdBy' field
        data['createdBy'] = user.name        
        data['patient'] = bill.patient #or visit.patient
        data['branch'] = bill.branch or data['patient'].branch
        
        return data


#Update transaction serializer -- PATCH only
class UpdateTransactionSerializer(TransactionSerializer):
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices,
                                   required=False, allow_blank=False, allow_null=False)
    status = TranslatedChoiceField(choices=Transaction.TransactionStatusChoices.choices,
                                   required=False, allow_blank=False, allow_null=False)
    
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'billId', 'date', 'amount', 'currency', 'method', 'type', 'status', 
                  'notes', 'updatedAt']
        read_only_fields = ['id', 'billId', 'type', 'updatedAt']

    def validate(self, data):
        #get current bill
        bill = getattr(self.instance, 'bill', None)
        
        #validate insurance is active and can cover transaction costs
        if bill and ('amount' in data or 'method' in data):
            amount = data.get('amount', self.instance.amount)
            method = data.get('method') or self.instance.method

            coverage = bill.patient.patient_insurance
            if coverage and (method == 'insurance')\
             and (amount and amount != self.instance.amount):
                updated_amount = amount - self.instance.amount
                coverage.validate_coverage_for_transaction(transaction_amount=updated_amount)
            
        return data


#Create deposit transaction serializer
class CreateDepositTransactionSerializer(ValidateBranchMixin, TransactionSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all())
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), allow_null=True)
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, 
                                   required=False, allow_blank=True, allow_null=True)
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'patientId', 'patientName', 'treatmentId', 'date', 'amount', 
                  'currency', 'method', 'type', 'notes', 'branchId']
        read_only_fields = ['id', 'patientName', 'type']

    def validate(self, data):
        #get current user
        user = self.context.get('request').user
        
        #fetch data for validation
        patient = data.get('patient')
        treatmentId = data.get('treatmentId')
        branch = data.get('branch') or patient.branch
        
        #Validate treatment 
        if treatmentId:
            try:
                treatment = TreatmentPlan.objects.only('id', 'patient')\
                    .select_related('patient').get(id=treatmentId)
            except (TreatmentPlan.DoesNotExist, Http404):
                raise serializers.ValidationError(_('Treatment plan was not found or does not exist.'))
            
            if not getattr(treatment, 'patient_id') or treatment.patient_id != patient.id:
                raise serializers.ValidationError({'treatmentId': _('Treatment plan does not belong to this patient.')})
        
        #Validate payment method
        if data.get('method', 'cash') == 'insurance':
            raise serializers.ValidationError(_('Insurance is not a valid payment method for deposit payments.'))

        #Auto-fill other data
        data['type'] = 'deposit'
        data['createdBy'] = user.name
        data['patient'] = patient
        data['branch'] = branch
        
        return data

    @transaction.atomic 
    def create(self, validated_data):
        #get patient and amount
        patient = validated_data['patient']
        amount = validated_data['amount']

        #Create settled bill to show in the payment records
        bill = Bill.objects.create(   #TODO - until frontend resolves this
            patient=patient,
            treatment_id=validated_data.get('treatmentId'),
            branch=validated_data.get('branch'),
            subtotal=amount,
            totalAmount=amount,
            totalPaid=amount,
            currency=validated_data.get('currency'),
            isCreditHeld=True,
            isDepositBill=True,
            description=(f"This bill was autogenerated after a {validated_data['amount']} deposit payment "
                         f"by {patient.name} on {validated_data['date']} to keep a record of the money "
                         f"withheld to be returned to the patient.")
        )

        #add bill to validated data
        validated_data['bill'] = bill

        #Call parent create method to create deposit transaction
        return super().create(validated_data)


#Refund transaction serializer
class RefundTransactionSerializer(TransactionSerializer):
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'billId', 'patientId', 'patientName', 'date', 'amount', 'currency', 
                  'method', 'type', 'status', 'refundReason', 'updatedAt']
        read_only_fields = ['id', 'billId', 'patientId', 'patientName', 'date', 'amount', 
                            'currency', 'method', 'type', 'status', 'updatedAt']
        extra_kwargs = {
            'refundReason': {'required': True, 'allow_blank': False, 'allow_null': False}
        }

    @transaction.atomic
    def update(self, instance, validated_data):
        refundReason = validated_data.get('refundReason')

        #update refunding reason and status
        instance.status = 'refunded'
        instance.refundReason = refundReason

        #save changes and return instance
        instance.save(update_fields=['status', 'refundReason', 'updatedAt'])
        return instance


#Serializer for requesting a correction
class RequestCorrectionSerializer(TransactionSerializer):
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'billId', 'patientId', 'patientName', 'date', 'amount', 'currency', 
                  'method', 'type', 'status', 'correctionReason', 'updatedAt']
        read_only_fields = ['id', 'billId', 'patientId', 'patientName', 'date', 'amount', 
                            'currency', 'method', 'type', 'status', 'updatedAt']
        extra_kwargs = {
            'correctionReason': {'required': True, 'allow_blank': False, 'allow_null': False}
        }
    
    @transaction.atomic
    def update(self, instance, validated_data):
        correctionReason = validated_data.get('correctionReason')

        #update correction reason and status
        instance.status = 'pending_correction'
        instance.correctionReason = correctionReason

        #save changes and return instance
        instance.save(update_fields=['status', 'correctionReason', 'updatedAt'])
        return instance


#Transactions options serializer
@transactions_options_schema
class TransactionsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    billChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    patientVisitChoices = serializers.SerializerMethodField()
    paymentMethodChoices = serializers.SerializerMethodField()
    transactionTypeChoices = serializers.SerializerMethodField()
    transactionStatusChoices = serializers.SerializerMethodField()

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
    def get_billChoices(self, obj):
        branchId = self.context.get('branchId')
        doctorId = self.context.get('doctorId')

        if (not branchId and Branch.objects.exists()) and not doctorId:
            return [] 
        
        filters = {}
        if branchId:
            filters['branch_id'] = branchId
        if doctorId:
            filters['patient__doctor_id'] = doctorId
        
        return [
            {'billId': bill_id}
             for bill_id in Bill.objects.filter(**filters)\
              .values_list('id', flat=True)
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
    def get_patientVisitChoices(self, obj):
        patientId = self.context.get('patientId')
        if not patientId:
            return []
        
        patient_filter = {'patient_id': patientId} if patientId else {}
        return [
            {'visitId': visit_id} 
            for visit_id in Visit.objects.filter(**patient_filter)\
             .values_list('id', flat=True)
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_paymentMethodChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Transaction.PaymentMethodChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_transactionTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Transaction.TransactionTypeChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_transactionStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Transaction.TransactionStatusChoices
        ]

