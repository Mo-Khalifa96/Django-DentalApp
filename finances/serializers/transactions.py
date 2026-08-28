from clinic.models import Branch
from rest_framework import serializers
from patients.models import Patient, Visit
from finances.models import Bill, Transaction
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField
from finances.docs import list_transactions_schema, transactions_options_schema


#Transactions serializer -- base serializer
@list_transactions_schema
class TransactionSerializer(serializers.ModelSerializer):
    billId = serializers.PrimaryKeyRelatedField(source='bill', read_only=True)
    visitId = serializers.PrimaryKeyRelatedField(source='visit', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, read_only=True)
    status = TranslatedChoiceField(choices=Transaction.TransactionStatusChoices.choices, read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'billId', 'billDescription', 'patientId', 'patientName', 'visitId', 'treatmentTitle', 
                  'branchId', 'branchName', 'date', 'amount', 'currency', 'method', 'status', 'note', 'createdBy', 
                  'isDeleted']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        #Remove snapshot fields for non-admins
        if request and getattr(request.user, 'role', None) != 'admin':
            fields.pop('billDescription', None)
            fields.pop('treatmentTitle', None)
            fields.pop('branchName', None)
            fields.pop('createdBy', None)
            fields.pop('status', None)
            fields.pop('isDeleted', None)
        return fields


#Create transaction serializer 
class CreateTransactionSerializer(TransactionSerializer):
    billId = serializers.PrimaryKeyRelatedField(source='bill', queryset=Bill.objects.all())
    visitId = serializers.PrimaryKeyRelatedField(source='visit', queryset=Visit.objects.all())
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, 
                                   required=False, allow_blank=True, allow_null=True)
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'billId', 'patientId', 'patientName', 'visitId', 'branchId', 
                  'date', 'amount', 'currency', 'method', 'note']
        read_only_fields = ['id', 'patientId', 'patientName','branchId']

    def validate(self, data):
        #Get request user 
        user = self.context.get('request').user
        
        #assign user's name to 'createdBy' field
        data['createdBy'] = user.name
        
        bill = data.get('bill')
        visit = data.get('visit')
        data['patient'] = bill.patient or visit.patient
        data['branch'] = bill.branch or data['patient'].branch
        
        return data


#Update transaction serializer
class UpdateTransactionSerializer(TransactionSerializer):
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices,
                                   required=False, allow_blank=False, allow_null=False)
    status = TranslatedChoiceField(choices=Transaction.TransactionStatusChoices.choices,
                                   required=False, allow_blank=False, allow_null=False)
    
    class Meta(TransactionSerializer.Meta):
        fields = ['id', 'billId', 'visitId', 'patientId', 'patientName', 'branchId', 
                  'date', 'amount', 'currency', 'method', 'status', 'note']
        read_only_fields = ['id', 'billId', 'visitId', 'patientId', 'patientName', 'branchId']
                


#Transactions options serializer
@transactions_options_schema
class TransactionsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    billChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    patientVisitChoices = serializers.SerializerMethodField()
    paymentMethodChoices = serializers.SerializerMethodField()

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

