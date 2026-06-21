import logging
from decimal import Decimal
from clinic.models import Branch
from django.utils import timezone
from django.db import transaction
from patients.models import Patient
from rest_framework import serializers
from utils.mixins import UserPermissionsMixin
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from finances.models import Bill, Invoice, InvoiceItem
from services.translation.serializers import TranslatedChoiceField
from finances.docs import list_invoices_schema, retrieve_invoice_schema, invoices_options_schema


#Initiate logger 
logger = logging.getLogger(__name__)


#INVOICES SERIALIZERS
#Invoice items serializer -- nested serializer
class InvoiceItemSerializer(serializers.ModelSerializer):
    code = serializers.ChoiceField(source='taxCode', choices=InvoiceItem.TaxCodeChoices.choices, 
                                   required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = InvoiceItem
        fields = ['code', 'description', 'quantity', 'unitPrice', 'total']
        extra_kwargs = {'total': {'required': False}}
    
    def validate(self, data):
        quantity = data.get('quantity', 1)
        unitPrice = data.get('unitPrice')
        total = data.get('total')

        recalculated_total = quantity * unitPrice
        if total and (round(recalculated_total,2) != round(total,2)\
         or abs(total - recalculated_total) > 0.01):
            logger.error(f'FRONTEND BUG: Total amount miscalculated. '
             f'Provided: {total}, Actual: {recalculated_total}')
        #assign recalculated total anyway
        data['total'] = recalculated_total

        return data
            
#Invoice serializer -- base serializer
@list_invoices_schema
class InvoiceSerializer(serializers.ModelSerializer):
    billId = serializers.PrimaryKeyRelatedField(source='bill', queryset=Bill.objects.all(), required=False, allow_null=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', queryset=Patient.objects.all(), required=False, allow_null=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    items = InvoiceItemSerializer(many=True, source='invoice_items', required=True, allow_empty=False)
    status = TranslatedChoiceField(choices=Invoice.InvoiceStatusChoices.choices, read_only=True)
    patientNationalId = serializers.CharField(source='patient.nationalId', read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'invoiceNumber','billId', 'billDescription', 'patientId', 'patientName', 
                  'patientNationalId', 'treatmentTitle', 'branchId', 'branchName', 'items', 
                  'subtotal', 'tax', 'discount', 'total', 'currency', 'status', 'issuedAt', 
                  'submittedAt', 'createdBy', 'createdAt', 'isDeleted']

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
    

#Retrieve invoice serializer
@retrieve_invoice_schema
class RetrieveInvoiceSerializer(UserPermissionsMixin, InvoiceSerializer):
    pass


#Create invoice serializer
class CreateInvoiceSerializer(InvoiceSerializer):
    class Meta(InvoiceSerializer.Meta):
        fields = ['id', 'invoiceNumber', 'billId', 'patientId', 'patientName', 'patientNationalId', 
                  'branchId', 'items', 'subtotal', 'tax', 'discount', 'total', 'currency', 'status', 
                  'issuedAt', 'submittedAt', 'createdAt']
        read_only_fields = ['id', 'invoiceNumber', 'patientName', 'patientNationalId', 'status', 
                            'issuedAt', 'submittedAt', 'createdAt']
        extra_kwargs = {'total': {'required': False}, 'currency': {'required': False}}
    
    def validate(self, data):
        #get current user 
        user = self.context['request'].user

        #assign user 
        data['createdBy'] = user.name

        #handle status
        if getattr(user, 'role', None) == 'admin':
            data['status'] = 'issued'
        else:
            data['status'] = 'submitted'

        #extract fields for validation
        bill = data.get('bill')
        items = data.get('invoice_items', [])
        tax = data.get('tax', Decimal('0'))
        discount = data.get('discount', Decimal('0'))
        subtotal = data.get('subtotal')
        total = data.get('total')


        #prepare errors dict
        errors = {}

        #handle patient 
        if bill and not data.get('patient'):
            data['patient'] = bill.patient

        #handle branch
        if not data.get('branch'):
            if bill:
                data['branch'] = bill.branch
            else:
                if user.branches.count() == 1:
                    data['branch'] = user.branches.first()
                elif getattr(user, 'branch_id', None):
                    data['branch'] = user.branch
                elif Branch.objects.exists():
                    errors['branchId'] = _('Clinic branch must be provided when at least one branch is registered. Please provide a branch ID or contact the admin to assign a branch to your account.')

    
        #validate subtotal against invoice items
        if items:
            recalculated_subtotal = sum(float(item['total']) for item in items if items)
            recalculated_subtotal = Decimal(str(recalculated_subtotal))
            if round(subtotal,2) != round(recalculated_subtotal,2)\
             or abs(subtotal - recalculated_subtotal) > 0.01:
                logger.error(f'FRONTEND BUG: Invoice subtotal provided does not match invoice items subtotal! '
                             f'Subtotal provided: {subtotal} - Subtotal calculated: {recalculated_subtotal}')
            
            #store recalculated subtotal anyway
            subtotal = recalculated_subtotal
            data['subtotal'] = subtotal
        
        #validate amount fields
        if discount > subtotal:
            errors['discount'] = _('Discount cannot exceed subtotal amount.')

        recalculated_total = subtotal + tax - discount
        if tax or discount:
            if total and (round(total,2) != round(recalculated_total,2)\
             or abs(total - recalculated_total) > 0.01):
                logger.error(f'FRONTEND BUG: Invoice total amount miscalculated. '
                             f'Provided: {total}, Actual: {recalculated_total}')
        else:
            if total and round(subtotal,2) != round(total,2):
                logger.error(f'FRONTEND BUG: Invoice total-subtotal mismatch. '
                             f'Total amount: {total}, Subtotal amount: {subtotal}')
                
        #assign the recalculated total anyway
        total = recalculated_total
        data['total'] = total 


        #Handle billing (if a bill is found)
        # if bill:
        #     if abs(subtotal - bill.subtotal) > 0.01:
        #         errors['subtotal'] = _("Invoice subtotal amount does not match bill's subtotal. If you need to customize the invoice independent of the bill, remove the bill or leave it empty.")
        #     if (not (tax or discount) or (discount and not tax)) and abs(total - bill.totalAmount) > 0.01:
        #         errors['total'] = _("Invoice total amount doesn't match bill's total. If you need to customize the invoice independent of the bill, remove the bill or leave it empty.")
            
        if errors:
            raise serializers.ValidationError(errors)

        return data
            

    @transaction.atomic
    def create(self, validated_data):
        #Handle invoice items creation manually
        items_data = validated_data.pop('invoice_items', [])
        
        #create current invoice
        invoice = Invoice.objects.create(**validated_data)
        
        #bulk create invoice items
        InvoiceItem.objects.bulk_create([
            InvoiceItem(invoice=invoice, **item)
            for item in items_data
        ])

        return invoice


#Update invoice serializer
class UpdateInvoiceSerializer(CreateInvoiceSerializer):    #PUT requests only
    billId = serializers.PrimaryKeyRelatedField(source='bill', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    status = TranslatedChoiceField(choices=Invoice.InvoiceStatusChoices.choices, 
                                   required=False, allow_blank=False, allow_null=False)

    class Meta(CreateInvoiceSerializer.Meta):
        fields = ['id', 'invoiceNumber', 'billId', 'patientId', 'patientName', 'patientNationalId',
                  'branchId', 'items', 'subtotal', 'tax', 'discount', 'total', 'currency', 'status', 
                  'issuedAt', 'submittedAt']
        read_only_fields = ['id', 'invoiceNumber', 'billId', 'patientId', 'patientName', 'patientNationalId',
                            'branchId']
        extra_kwargs = {'status': {'required': False}, 'total': {'required': False}, 'discount': {'required': False}, 
                        'tax': {'required': False}, 'currency': {'required': False}, 'status': {'required': False}}


    def validate(self, data):
        #extract fields for validation
        items = data.get('invoice_items', [])
        tax = data.get('tax', Decimal('0'))
        discount = data.get('discount', Decimal('0'))
        subtotal = data.get('subtotal')
        total = data.get('total')
        status = data.get('status')
        issuedAt = data.get('issuedAt')

        #handle invoice issue date (submittedAt is handled in the model's save() method)
        if status and status == Invoice.InvoiceStatusChoices.ISSUED and not issuedAt:
            data['issuedAt'] = timezone.localtime(timezone.now())
        
        #validate subtotal against invoice items
        if items:
            recalculated_subtotal = sum(float(item['total']) for item in items if items)
            recalculated_subtotal = Decimal(str(recalculated_subtotal))
            if round(subtotal,2) != round(recalculated_subtotal,2)\
             or abs(subtotal - recalculated_subtotal) > 0.01:
                logger.error(f'FRONTEND BUG: Invoice subtotal provided does not match invoice items subtotal! '
                             f'Subtotal provided: {subtotal} - Subtotal calculated: {recalculated_subtotal}')
            
            #store recalculated subtotal anyway
            subtotal = recalculated_subtotal
            data['subtotal'] = subtotal
        
        #validate amount fields
        if 'discount' in data and discount > subtotal:
            raise serializers.ValidationError({'discount': 'Discount cannot exceed subtotal amount.'})

        recalculated_total = subtotal + tax - discount
        if tax or discount:
            if total and (round(total,2) != round(recalculated_total,2)\
             or abs(total - recalculated_total) > 0.01):
                logger.error(f'FRONTEND BUG: Invoice total amount miscalculated. '
                             f'Provided: {total}, Actual: {recalculated_total}')
        else:
            if total and round(subtotal,2) != round(total,2):
                logger.error(f'FRONTEND BUG: Invoice total-subtotal mismatch. '
                             f'Total amount: {total}, Subtotal amount: {subtotal}')
                
        #assign the recalculated total anyway
        total = recalculated_total
        data['total'] = total

        return data


    @transaction.atomic
    def update(self, instance, validated_data):
        #fetch updated items (if any)
        updated_items = validated_data.pop('invoice_items', None)

        #delete and update items 
        if updated_items is not None:
            #delete existing items and recreate 
            instance.invoice_items.all().delete()

            #recreate invoice items from passed data
            InvoiceItem.objects.bulk_create([
                InvoiceItem(invoice=instance, **item)
                 for item in updated_items
            ])

        #Update remaining fields
        for field, value in validated_data.items():
            setattr(instance, field, value)   #i.e. instance.field = value

        #update instance
        instance.save()
        return instance



#Update invoice status only serializer
class UpdateInvoiceStatusSerializer(serializers.ModelSerializer):   #PATCH requests only
    status = TranslatedChoiceField(choices=Invoice.InvoiceStatusChoices.choices, 
                                required=False, allow_blank=False, allow_null=False)

    class Meta:
        model = Invoice 
        fields = ['status', 'issuedAt', 'submittedAt']
    
    def validate(self, data):
        status = data.get('status')
        issuedAt = data.get('issuedAt')
        if status and status == Invoice.InvoiceStatusChoices.ISSUED and not issuedAt:
            data['issuedAt'] = timezone.localtime(timezone.now())
        return data


#Invoices options serializer
@invoices_options_schema
class InvoicesOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    billChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    invoiceStatusChoices = serializers.SerializerMethodField()
    taxCodeChoices = serializers.SerializerMethodField()

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
        
        filters = {}
        if branchId:
            filters['branch_id'] = branchId
        if doctorId:
            filters['doctor_id'] = doctorId
        
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
    def get_invoiceStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Invoice.InvoiceStatusChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_taxCodeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in InvoiceItem.TaxCodeChoices
        ]




