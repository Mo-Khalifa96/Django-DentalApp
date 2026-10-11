import logging
from decimal import Decimal
from django.db.models import Q
from clinic.models import Branch
from django.utils import timezone
from django.db import transaction
from patients.models import Patient
from rest_framework import serializers
from utils.mixins import UserPermissionsMixin
from dateutil.relativedelta import relativedelta
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from utils.exceptions import InstallmentPlanInProgressError
from services.translation.serializers import TranslatedChoiceField
from finances.models import Bill, Transaction, InstallmentPlan, Installment
from finances.docs import retrieve_installments_transaction_schema, installments_options_schema


#Initiate logger 
logger = logging.getLogger(__name__)


#INSTALLMENTS SERIALIZERS
#Installments serializer -- base serializer
class InstallmentsSerializer(serializers.ModelSerializer):
    status = TranslatedChoiceField(choices=Installment.InstallmentStatusChoices.choices, read_only=True)
    type = TranslatedChoiceField(choices=Installment.InstallmentTypeChoices.choices, read_only=True)
    transactionId = serializers.PrimaryKeyRelatedField(source='transaction', read_only=True)
    
    class Meta:
        model = Installment
        fields = ['id', 'amount', 'sequence', 'dueDate', 'type', 'status', 'paidAt', 'transactionId']


#Installment plan serializer -- base serializer (& List installments serializer)
class InstallmentPlanSerializer(serializers.ModelSerializer):
    installmentPlanId = serializers.UUIDField(source='id', read_only=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='treatment', read_only=True)
    treatmentTitle = serializers.CharField(source='treatment.title', read_only=True)
    billId = serializers.SerializerMethodField()
    patientId = serializers.PrimaryKeyRelatedField(source='treatment.patient', read_only=True)
    patientName = serializers.CharField(source='treatment.patient.name', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    status = TranslatedChoiceField(choices=InstallmentPlan.InstallmentPlanStatusChoices.choices, read_only=True)
    installmentMonths = TranslatedChoiceField(choices=InstallmentPlan.InstallmentMonthsChoices.choices)
    installments = InstallmentsSerializer(many=True, read_only=True)

    class Meta:
        model = InstallmentPlan
        fields = ['installmentPlanId', 'patientId', 'patientName', 'treatmentId', 'treatmentTitle', 
                  'billId', 'installmentMonths', 'startDate', 'totalAmount', 'totalPaid', 
                  'status', 'installments', 'branchId', 'createdAt', 'updatedAt']

    @extend_schema_field(serializers.UUIDField())
    def get_billId(self, obj):
        bill = obj.active_bill
        return bill.id if bill else None

#Retrieve installments serializer -- nested serializer
class RetrievePatientInstallmentsSerializer(InstallmentsSerializer):
    status = serializers.SerializerMethodField()
    
    class Meta(InstallmentsSerializer.Meta):
        model = Installment
        fields = ['id', 'amount', 'sequence', 'dueDate', 'type', 'status', 'paidAt', 'transactionId']

    @extend_schema_field(
        serializers.ChoiceField(
            choices=[(choice,choice) for choice in Installment.InstallmentStatusChoices.choices]
        )
    )
    def get_status(self, obj):
        if obj.paidAt:
            return Installment.InstallmentStatusChoices.PAID
        elif obj.dueDate < timezone.localdate(timezone.now()):
            return Installment.InstallmentStatusChoices.OVERDUE
        else:
            return Installment.InstallmentStatusChoices.PENDING
       

#Retrieve installment plan serializer
class RetrievePatientInstallmentPlanSerializer(InstallmentPlanSerializer):
    status = serializers.SerializerMethodField()
    installments = RetrievePatientInstallmentsSerializer(many=True, read_only=True)

    class Meta(InstallmentPlanSerializer.Meta):
        fields = ['installmentPlanId', 'treatmentId', 'billId', 'installmentMonths', 'startDate',
                'totalAmount', 'totalPaid', 'status', 'installments', 'createdAt', 'updatedAt']

    @extend_schema_field(
        serializers.ChoiceField(
            choices=[(choice,choice) for choice in InstallmentPlan.InstallmentPlanStatusChoices.choices]
        )
    )
    def get_status(self, obj):
        if not obj.totalPaid:
            return InstallmentPlan.InstallmentPlanStatusChoices.PENDING
        elif obj.totalPaid >= obj.totalAmount:
            return InstallmentPlan.InstallmentPlanStatusChoices.COMPLETED
        else:
            return InstallmentPlan.InstallmentPlanStatusChoices.PARTIAL
       

#Generate installments serializer -- nested serializer
class GenerateInstallmentsSerializer(InstallmentsSerializer):
    status = serializers.SerializerMethodField()

    class Meta(InstallmentsSerializer.Meta):
        fields = ['id', 'amount', 'sequence', 'dueDate', 'type', 'status']

    @extend_schema_field(
        serializers.ChoiceField(
            choices=[(choice,choice) for choice in Installment.InstallmentStatusChoices.choices]
        )
    )
    def get_status(self, obj):
        if obj.paidAt:
            return Installment.InstallmentStatusChoices.PAID
        elif obj.dueDate < timezone.localdate(timezone.now()):
            return Installment.InstallmentStatusChoices.OVERDUE
        else:
            return Installment.InstallmentStatusChoices.PENDING

#Generate installment plan serializer
class GenerateInstallmentPlanSerializer(InstallmentPlanSerializer):
    status = serializers.SerializerMethodField()
    installments = GenerateInstallmentsSerializer(many=True, read_only=True)

    class Meta(InstallmentPlanSerializer.Meta):
        fields = ['installmentPlanId', 'treatmentId', 'installmentMonths', 'startDate',
                'downPayment', 'totalAmount', 'totalPaid', 'status', 'installments', 'createdAt']
        read_only_fields = ['installmentPlanId', 'treatmentId', 'totalAmount', 'totalPaid', 
                            'status', 'installments', 'createdAt']
        extra_kwargs = {'downPayment': {'write_only': True, 'required': False, 'allow_null': True}}


    @extend_schema_field(
        serializers.ChoiceField(
            choices=[(choice,choice) for choice in InstallmentPlan.InstallmentPlanStatusChoices.choices]
        )
    )
    def get_status(self, obj):
        if not obj.totalPaid:
            return InstallmentPlan.InstallmentPlanStatusChoices.PENDING
        elif obj.totalPaid >= obj.totalAmount:
            return InstallmentPlan.InstallmentPlanStatusChoices.COMPLETED
        else:
            return InstallmentPlan.InstallmentPlanStatusChoices.PARTIAL
    

    def validate(self, data):
        #get treatment treatment from context
        treatment = self.context.get('treatment')

        #Validate the treatment doesn't already have a plan with paid installments
        if getattr(treatment, 'installment_plan', None):
            installments = treatment.installment_plan.installments.all()
            if installments.filter(type='installment', paidAt__isnull=False).exists():
                raise InstallmentPlanInProgressError(
                    detail=_('An installment plan already exists for this treatment plan with paid installments marked as complete.')
                )
            
            #add any previous downpayment to total paid
            # if installments.filter(type=Installment.InstallmentTypeChoices.DOWN_PAYMENT, paidAt__isnull=False).exists():
            #     # data['totalPaid'] = Decimal(str((treatment.installment_plan.totalPaid or Decimal('0')) + treatment.installment_plan.downPayment))
            #     # data['totalPaid'] = Decimal(str((treatment.installment_plan.downPayment if not treatment.installment_plan.totalPaid else treatment.installment_plan.totalPaid)))
            #     data['totalAmount'] = treatment.totalCost #- data['totalPaid']))    
    
        #assign treatment id to data
        data['treatment'] = treatment
        return data 

    @transaction.atomic
    def create(self, validated_data):
        #Fetch data for creating the plan
        treatment = validated_data['treatment']
        existing_plan = getattr(treatment, 'installment_plan', None)
        installmentMonths = validated_data['installmentMonths']
        startDate = validated_data['startDate']
        downPayment = validated_data.get('downPayment') or Decimal('0')
        total_amount = treatment.totalCost
        # total_paid = treatment.installment_plan.totalPaid or Decimal('0')
        total_paid = getattr(existing_plan, 'totalPaid', None) or Decimal('0')
        total_remaining = total_amount - total_paid

        #Create installment plan
        plan, created = InstallmentPlan.objects.update_or_create(
             treatment_id=treatment.id,
             defaults={
                'installmentMonths': installmentMonths,
                'startDate': startDate,
                'downPayment': downPayment,
                'totalAmount': total_amount,
                # 'totalPaid': total_paid,
                'currency': treatment.currency,
                'branch': treatment.patient.branch
            }
        )

        #fetch the down payment row separately (if found)
        seq0_installment = plan.installments.filter(sequence=0).first() #if plan.installments else None
        
        #Bulk create installments according to plan
        installments_to_create = []
        for n in range(installmentMonths+1):
            # sequence = n
            if n == 0:
                if downPayment > 0:
                    #iteratively determine amount, due date, and type
                    amount = downPayment
                    installment_type = 'down_payment'
                    #determine due date from payload or old plan
                    if (created == False) and seq0_installment:
                        dueDate = seq0_installment.dueDate
                    else:
                        dueDate = timezone.localdate(timezone.now())
                else:
                    continue  #skip this iteration
            else:
                amount = Decimal(str(total_remaining / installmentMonths))
                installment_type = 'installment'
                dueDate = startDate + relativedelta(months=n)

            #create installments iteratively
            installments_to_create.append(
                Installment(
                    installmentPlan=plan,
                    amount=amount,
                    sequence=n,
                    dueDate=dueDate,
                    type=installment_type
                )
            )
        
        #bulk create (or update) installments
        Installment.objects.bulk_create(
            installments_to_create,
            update_conflicts=True,  #enable updating of existing records
            unique_fields=['installmentPlan', 'sequence'],  #lookup/unique constraints fields
            update_fields=['amount', 'dueDate', 'type'],  #fields to update if installment already exists
        )


        #delete excess installments if the number of installments shrank
        if created == False:
            plan.installments.filter(sequence__gt=installmentMonths).delete()

        if 'downPayment' in validated_data:   #If update and down payment is provided
            if not validated_data.get('downPayment'):  #sent but None/0 --> meant for intentional removal
                # if not getattr(seq0_installment, 'paidAt', None): #if old down payment doesn't exist or exists but not paid
                plan.installments.filter(sequence=0).delete()
            else:  #else a down payment was given
                #new down payment shouldn't have a transaction or paidAt date
                plan.installments.filter(sequence=0).update(paidAt=None, transaction=None)


        #see if the associated bill needs to be updated
        if plan.active_bill:
            #update total amount
            plan.active_bill.totalAmount = total_amount
            plan.active_bill.save(update_fields=['totalAmount'])
        
        return plan


#Update installment plan serializer --> PATCH api/patients/.../installments/ and PATCH api/installments/{id}/
class UpdateInstallmentPlanSerializer(InstallmentPlanSerializer):
    status = serializers.SerializerMethodField()
    installments = GenerateInstallmentsSerializer(many=True, read_only=True)

    class Meta(InstallmentPlanSerializer.Meta):
        fields = ['installmentPlanId', 'treatmentId', 'installmentMonths', 'startDate',
                'downPayment', 'totalAmount', 'totalPaid', 'status', 'installments', 'updatedAt']
        read_only_fields = ['installmentPlanId', 'treatmentId', 'totalAmount', 'totalPaid', 
                            'status', 'installments', 'updatedAt']
        extra_kwargs = {'downPayment': {'write_only': True, 'required': False, 'allow_null': True}}

    @extend_schema_field(
        serializers.ChoiceField(
            choices=[(choice,choice) for choice in InstallmentPlan.InstallmentPlanStatusChoices.choices]
        )
    )
    def get_status(self, obj):
        if not obj.totalPaid:
            return InstallmentPlan.InstallmentPlanStatusChoices.PENDING
        elif obj.totalPaid >= obj.totalAmount:
            return InstallmentPlan.InstallmentPlanStatusChoices.COMPLETED
        else:
            return InstallmentPlan.InstallmentPlanStatusChoices.PARTIAL
    

    def validate(self, data):
        #get current plan instance 
        installment_plan = self.instance

        #Validate the installment plan doesn't already have paid installments
        installments = installment_plan.installments.all()
        if installments.filter(type='installment', paidAt__isnull=False).exists():
            raise InstallmentPlanInProgressError(
                detail=_('This installment plan cannot be modified because one or more installments have already been paid.')
            )
        
        #add any previous downpayment to total paid
        # if installments.filter(type=Installment.InstallmentTypeChoices.DOWN_PAYMENT, paidAt__isnull=False).exists():
        #     data['totalPaid'] = Decimal(str((installment_plan.totalPaid or Decimal('0')) + installment_plan.downPayment))
        #     # data['totalPaid'] = Decimal(str((installment_plan.downPayment if not installment_plan.totalPaid else installment_plan.totalPaid)))
        #     data['totalAmount'] = Decimal(str(installment_plan.totalAmount)) #- data['totalPaid']))

        return data 

    @transaction.atomic
    def update(self, instance, validated_data):
        #Fetch data for updating the plan
        installmentMonths = validated_data.get('installmentMonths', instance.installmentMonths)
        startDate = validated_data.get('startDate', instance.startDate)
        downPayment = validated_data.get('downPayment', instance.downPayment)

        # total_amount = validated_data.get('totalAmount', instance.totalAmount)
        # total_paid = instance.totalPaid or Decimal('0')
        # total_paid = validated_data.get('totalPaid', instance.totalPaid) or Decimal('0')
        total_remaining = instance.totalAmount - (instance.totalPaid or Decimal('0'))

        #fetch the down payment row separately (if found)
        seq0_installment = instance.installments.filter(sequence=0).first()

        #update instance values 
        instance.installmentMonths = installmentMonths
        instance.startDate = startDate
        instance.downPayment = downPayment
        # instance.totalAmount = total_amount
        # instance.totalPaid = total_paid

        #save new changes
        instance.save()

        #update installments given new data
        installments_to_update = []
        for n in range(installmentMonths+1):
            if n == 0:
                if downPayment > 0:
                    amount = downPayment
                    installment_type = 'down_payment'
                    #determine due date from payload or old plan
                    if 'downPayment' in validated_data:
                       dueDate = timezone.localdate(timezone.now())
                    elif seq0_installment:
                        dueDate = seq0_installment.dueDate
                    else:
                        dueDate = timezone.localdate(timezone.now())
                else:
                    continue  #skip this iteration
            else:
                amount = Decimal(str(total_remaining / installmentMonths))
                installment_type = 'installment'
                dueDate = startDate + relativedelta(months=n)
            
            #update iteratively
            installments_to_update.append(
                Installment(
                    installmentPlan=instance,
                    amount=amount,
                    sequence=n,
                    dueDate=dueDate,
                    type=installment_type,
                )
            )
        
        #bulk create/update
        Installment.objects.bulk_create(
            installments_to_update,
            update_conflicts=True,  #enable updating of existing records
            unique_fields=['installmentPlan', 'sequence'],  #lookup/unique constraints fields
            update_fields=['amount', 'dueDate', 'type']  #fields to update if installment already exists
        )

        #delete excess installments if the number of installments shrank
        instance.installments.filter(sequence__gt=installmentMonths).delete()

        #determine if the downpayment is to be removed too
        if 'downPayment' in validated_data:  #If update and down payment is provided
            if not validated_data.get('downPayment'):   #sent but None/0 --> meant for 
                # if not getattr(seq0_installment, 'paidAt', None):  #if old down payment doesn't exist or exists but not paid
                instance.installments.filter(sequence=0).delete()
            else:  #else a down payment was given
                #new down payment shouldn't have a transaction or paidAt date
                instance.installments.filter(sequence=0).update(paidAt=None, transaction=None)

        #update associated bill
        # if instance.active_bill:
        #     instance.active_bill.totalAmount = total_amount
        #     instance.active_bill.totalPaid = total_paid
        #     instance.active_bill.save(update_fields=['totalAmount', 'totalPaid'])
        
        #return updated instance
        return instance


#Auto-generate installments bill serializer
class AutogenerateInstallmentsBillSerializer(serializers.ModelSerializer):
    billId = serializers.UUIDField(source='id', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='treatment', read_only=True)
    installmentPlanId = serializers.PrimaryKeyRelatedField(source='installmentPlan', queryset=InstallmentPlan.objects.all(), required=False)
    installmentIds = serializers.PrimaryKeyRelatedField(source='installmentPlan.installments', read_only=True)
    installmentMonths = serializers.IntegerField(source='installmentPlan.installmentMonths', read_only=True)
    startDate = serializers.DateField(source='installmentPlan.startDate', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    
    class Meta:
        model = Bill
        fields = ['billId', 'patientId', 'patientName', 'treatmentId', 'installmentPlanId', 
                  'installmentIds', 'description', 'installmentMonths', 'startDate', 
                  'totalAmount', 'totalPaid', 'currency', 'branchId', 'createdAt']
        read_only_fields = ['billId', 'patientId', 'patientName', 'treatmentId',
                  'installmentIds', 'description', 'installmentMonths', 'startDate', 
                  'totalAmount', 'totalPaid', 'currency', 'branchId', 'createdAt']

    def validate_installmentPlanId(self, plan):
        #validate passed installment plan id against plan from url
        req_path = self.context.get('request').path
        plan_from_path = self.context.get('installment_plan')
        if plan and (plan.id != plan_from_path.id):
            if 'treatment-plans' in req_path:
                error_detail = _('This installment plan does not belong to the current treatment.')
            else:
                error_detail = _('Installment plan id mismatch. The installment plan might be deleted or does not exist. '
                                 'If you believe this not to be the case, please contact the support team immediately.')
            raise serializers.ValidationError(error_detail)
        return plan

    @transaction.atomic
    def create(self, validated_data):
        #get installment plan from context
        installment_plan = self.context.get('installment_plan')
        treatment = installment_plan.treatment
        description = f'Installment plan for {(treatment.title if treatment.title else (treatment.patient.name + '\'s'))} treatment'
        
        #Update or create bill
        bill, _ = Bill.objects.update_or_create(
            installmentPlan_id=installment_plan.id,
            patient_id=treatment.patient.id,
            treatment_id=treatment.id,
            defaults={
                'description': description,
                'subtotal': installment_plan.totalAmount,
                'totalAmount': installment_plan.totalAmount,
                'totalPaid': installment_plan.totalPaid,
                'currency': installment_plan.currency,
                'branch': treatment.patient.branch,
                'updatedAt': timezone.localtime(timezone.now())
            }
        )

        return bill


#Create installment(s) transaction serializer
class CreateInstallmentTransactionSerializer(serializers.ModelSerializer):
    #read-only
    transactionId = serializers.UUIDField(source='id', read_only=True)  #TODO - document new field
    billId = serializers.PrimaryKeyRelatedField(source='bill', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='bill.treatment', read_only=True)
    installmentPlanId = serializers.PrimaryKeyRelatedField(source='bill.installmentPlan', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    type = TranslatedChoiceField(choices=Transaction.TransactionTypeChoices.choices, read_only=True)
    #read/write
    installmentIds = serializers.PrimaryKeyRelatedField(many=True, source='installments', queryset=Installment.objects.all(), allow_empty=False)
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, 
                                   required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Transaction
        fields = ['transactionId', 'billId', 'patientId', 'patientName', 'treatmentId', 'installmentPlanId', 
                  'installmentIds', 'branchId', 'date', 'amount', 'currency', 'method', 'type', 'notes']
        read_only_fields = ['transactionId', 'billId', 'patientId', 'patientName', 'treatmentId',
                            'installmentPlanId', 'branchId', 'amount', 'currency', 'type']
        #read/write --> installmentIds, date, method, notes

    def validate(self, data):
        #fetch necessary data for validation
        installments = data.get('installments')
        plan = self.context.get('installment_plan')  #passed from serializer context
        bill = plan.active_bill
        
        #Validate current plan has a bill
        if not bill:
            raise serializers.ValidationError({'non_field_errors': [_(f'The installment plan to which these installments belong does not have a corresponding bill. '
                                                                      f'Make sure a bill is generated for the associated installment plan first before making a transaction.')]})

        lowest_sequence = None
        total_from_installments = 0
        for installment in installments:
            #determine lowest sequence
            if lowest_sequence is None or installment.sequence < lowest_sequence:
                lowest_sequence = installment.sequence
            
            #validate if an installment has already been paid 
            if installment.paidAt:
                raise serializers.ValidationError({'installmentIds': _('At least one or more of the chosen installments has already been paid.')})
                    
            #validate the passed installments belong to the plan in the url
            if installment.installmentPlan.id != plan.id:
                raise serializers.ValidationError({'installmentIds': _('At least one or more of the chosen installments does not belong to the current installment plan.')})

            #add installment's amount to total
            total_from_installments = total_from_installments + installment.amount

        #convert total amount to decimal
        total_from_installments = Decimal(str(total_from_installments))
        
        #Validate order of installments
        #validate if earlier pending installments are excluded from installments sent
        if plan.installments.filter(paidAt__isnull=True, sequence__lt=lowest_sequence).exists():
            raise serializers.ValidationError({'installmentIds': _('Installments must be paid in sequence according to the installment plan. '
                                                                    'Please select installments with the earliest due dates first before paying '
                                                                    'subsequent ones.')})


        #validate insurance is active and can cover transaction costs
        coverage = bill.patient.patient_insurance
        if coverage and data.get('method') == 'insurance':
              coverage.validate_coverage_for_transaction(transaction_amount=total_from_installments)

        #assign the calculated total and currency
        data['amount'] = total_from_installments
        data['currency'] = bill.currency
        return data 
    
    @transaction.atomic
    def create(self, validated_data):
        #fetch necessary data for the transactions
        user = self.context.get('request').user
        total_amount = validated_data.get('amount')
        installments = validated_data.get('installments')
        plan = self.context.get('installment_plan')  #passed from serializer context
        bill = plan.active_bill
        datetime_now = timezone.localtime(timezone.now())

        #Create transaction 
        transaction = Transaction.objects.create(
                        patient=bill.patient,
                        patientName=bill.patient.name,
                        bill=bill,
                        billDescription=bill.description,
                        amount=total_amount,
                        date=validated_data['date'],
                        currency=validated_data['currency'],
                        method=(validated_data.get('method') or 'cash'),
                        notes=validated_data.get('notes'),
                        status='completed',
                        type='installment',
                        treatmentTitle=(bill.treatmentTitle or getattr(plan.treatment, 'title', None)),
                        branch=(bill.branch or bill.patient.branch),
                        branchName=(getattr(bill.branch, 'name', None) or getattr(bill.patient.branch, 'name', None)),
                        createdBy=user.name
                    )    

        #Set installments' paidAt and transactionId
        for installment in installments:
            installment.transaction_id = transaction.id
            installment.paidAt = datetime_now
        
        #Bulk update installments
        Installment.objects.bulk_update(installments, fields=['transaction', 'paidAt'])
        
        #return current transaction instance
        return transaction


#Installments settled serializer -- nested serializer 
class InstallmentsSettledSerializer(InstallmentsSerializer):
    class Meta(InstallmentsSerializer.Meta):
        fields = ['id', 'amount', 'sequence', 'dueDate', 'type']

#Retrieve installment(s) transaction serializer 
@retrieve_installments_transaction_schema
class RetrieveInstallmentTransactionSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    transactionId = serializers.UUIDField(source='id', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    billId = serializers.PrimaryKeyRelatedField(source='bill', read_only=True)
    treatmentId = serializers.PrimaryKeyRelatedField(source='bill.treatment', read_only=True)
    installmentPlanId = serializers.PrimaryKeyRelatedField(source='bill.installmentPlan', read_only=True)
    installmentsPaid = InstallmentsSettledSerializer(many=True, source='installments', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    type = TranslatedChoiceField(choices=Transaction.TransactionTypeChoices.choices, read_only=True)
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, read_only=True)
    status = TranslatedChoiceField(choices=Transaction.TransactionStatusChoices.choices, read_only=True)

    class Meta:
        model = Transaction
        fields = ['transactionId', 'billId', 'billDescription', 'patientId', 'patientName', 'treatmentId', 
                  'treatmentTitle', 'installmentPlanId', 'installmentsPaid', 'date', 'amount', 'currency', 
                  'method', 'type', 'status', 'notes', 'refundReason', 'correctionReason', 'createdBy', 
                  'branchId', 'branchName', 'isDeleted']


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


#Update installment(s) transaction serializer -- PUT only
class UpdateInstallmentTransactionSerializer(CreateInstallmentTransactionSerializer):
    method = TranslatedChoiceField(choices=Transaction.PaymentMethodChoices.choices, 
                                   required=False, allow_blank=False, allow_null=False)
    status = TranslatedChoiceField(choices=Transaction.TransactionStatusChoices.choices,
                                   required=False, allow_blank=False, allow_null=False)

    class Meta(CreateInstallmentTransactionSerializer.Meta):
        fields = ['transactionId', 'billId', 'treatmentId', 'installmentPlanId', 'installmentIds', 
                  'date', 'amount', 'currency', 'method', 'type', 'status', 'notes', 'updatedAt']
        read_only_fields = ['transactionId', 'billId', 'treatmentId', 'installmentPlanId',
                            'amount', 'currency', 'type', 'updatedAt']
        # extra_kwargs = {'amount': {'required': False}}
        #read/write --> installmentIds, date,  method, status, notes

    def validate(self, data):
        #fetch necessary data for validation
        bill = getattr(self.instance, 'bill', None)
        installments = data.get('installments')
        
        #Validate current plan has a bill
        if not bill or bill.isDeleted:
            raise serializers.ValidationError({'non_field_errors': [
                _(f'The installment plan to which these installments belong does not have a corresponding bill. '
                  f'The bill may have been removed or deleted. Make sure a bill is generated for the installment plan before updating.')
            ]})
        
        #get plan from bill
        plan = bill.installmentPlan


        ids_list = []
        lowest_sequence = None
        total_from_installments = 0
        for installment in installments:
            #add installment id
            ids_list.append(installment.id)

            #determine lowest sequence
            if lowest_sequence is None or installment.sequence < lowest_sequence:
                lowest_sequence = installment.sequence
            
            if installment.paidAt and (installment.transaction_id != self.instance.id):
                raise serializers.ValidationError({
                    'installmentIds': _('At least one or more of the chosen installments has already been paid '
                                        'through a different transaction.')})
                    
            #add installment's amount to total
            total_from_installments = total_from_installments + installment.amount

        #convert total amount to decimal
        total_from_installments = Decimal(str(total_from_installments))
        
        #Validate order of installments
        #validate if pending installments earlier in the sequence were excluded (account for installments about to lose their 'paid' status)
        if plan.installments.exclude(id__in=ids_list)\
         .filter(Q(paidAt__isnull=True) | Q(transaction_id=self.instance.id), sequence__lt=lowest_sequence)\
         .exists():
            raise serializers.ValidationError({'installmentIds': _('Installments must be paid in sequence according to the installment plan. '
                                                                    'Please select installments with the earliest due dates first before paying '
                                                                    'subsequent ones.')})


        #validate insurance is active and can cover transaction costs
        coverage = bill.patient.patient_insurance
        if coverage and data.get('method') == 'insurance'\
         and (total_from_installments != self.instance.amount):
            amount_diff = total_from_installments - self.instance.amount
            coverage.validate_coverage_for_transaction(transaction_amount=amount_diff)
        
        #pass over data for updating
        data['amount'] = total_from_installments
        data['currency'] = bill.currency
        data['installment_ids'] = ids_list
        return data

    @transaction.atomic 
    def update(self, instance, validated_data):
        #fetch current installments (and ids list)
        installments = validated_data.pop('installments')
        installments_ids = validated_data.pop('installment_ids')

        #update removed installments' transaction and paid date (if any)
        excluded_installments = instance.installments.exclude(id__in=installments_ids)
        excluded_installments.update(paidAt=None, transaction=None)

        #update transaction fields with new values
        for field, value in validated_data.items():
            setattr(instance, field, value)  #i.e. instance.field = value

        #save changes
        instance.save()


        #get datetime now
        datetime_now = timezone.localtime(timezone.now())        
        #set installments' paidAt and transactionId
        for installment in installments:
            if getattr(installment, 'transaction_id', None) != instance.id:
                installment.transaction_id = instance.id
                installment.paidAt = datetime_now
        
        #Bulk update installments
        Installment.objects.bulk_update(installments, fields=['transaction', 'paidAt'])

        #return updated instance
        return instance


#Installment options serializer 
@installments_options_schema
class InstallmentsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    patientPendingInstallments = serializers.SerializerMethodField()
    InstallmentPlanStatusChoices = serializers.SerializerMethodField()
    installmentMonthsChoices = serializers.SerializerMethodField()
    installmentTypeChoices = serializers.SerializerMethodField()
    installmentStatusChoices = serializers.SerializerMethodField()
    paymentMethodChoices = serializers.SerializerMethodField()
    transactionTypeChoices = serializers.SerializerMethodField()
    
    
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_branchChoices(self, obj):
        return [
            {'branchId': branch_id, 'name': name} 
              for branch_id,name in Branch.objects\
               .values_list('id', 'name').order_by('name')
            ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
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
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_patientPendingInstallments(self, obj):
        installmentPlanId = self.context.get('installmentPlanId')
        if not installmentPlanId:
            return []
        
        plan_filter = {'installmentPlan_id': installmentPlanId, 'paidAt__isnull': True}
        return [
            {
                'id': installment_id,
                'amount': amount,
                'sequence': sequence,
                'dueDate': dueDate,
                'type': installment_type,
            } for installment_id, amount, sequence, dueDate, installment_type
                in Installment.objects.filter(**plan_filter).values_list(
                    'id', 'amount', 'sequence', 'dueDate', 'type'
                ).order_by('sequence')
        ]


    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_InstallmentPlanStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in InstallmentPlan.InstallmentPlanStatusChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_installmentMonthsChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in InstallmentPlan.InstallmentMonthsChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_installmentTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Installment.InstallmentTypeChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_installmentStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Installment.InstallmentStatusChoices
        ]
         
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_paymentMethodChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Transaction.PaymentMethodChoices
        ]
        

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        )
    )
    def get_transactionTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Transaction.TransactionTypeChoices
        ]
        
