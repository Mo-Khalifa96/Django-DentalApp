import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction 
from rest_framework import serializers
from patients.utils import TEETH_CHOICES
from clinic.models import Branch, Procedure
from utils.mixins import UserPermissionsMixin
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from patients.docs import treatmentplans_options_schema
from finances.models import InstallmentPlan, Installment
from patients.models import TreatmentPlan, TreatmentPlanItem
from services.translation.serializers import TranslatedChoiceField


#Initiate logger 
logger = logging.getLogger(__name__)


#SERIALIZERS FOR TREATMENT PLANS 
#Treatment plan items serializer --  Nested serializer
class TreatmentPlanItemsSerializer(serializers.ModelSerializer):
    procedureId = serializers.PrimaryKeyRelatedField(source='procedure', queryset=Procedure.objects.all())
    status = TranslatedChoiceField(choices=TreatmentPlanItem.ItemStatusChoices.choices,
                                   required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = TreatmentPlanItem
        fields = ['id', 'procedureId', 'procedureName', 'toothNumber', 'price', 'session', 'status', 'notes']
        read_only_fields = ['id', 'procedureName']


#Base treatment plans serializer for retrieving patient procedure and treatment plan
class TreatmentPlanSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    items = TreatmentPlanItemsSerializer(many=True, source='treatment_items', required=True, allow_empty=False)
    status = TranslatedChoiceField(choices=TreatmentPlan.TreatmentStatusChoices.choices,
                                   required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = TreatmentPlan
        fields = ['id', 'patientId', 'title', 'status', 'items', 'currency', 'totalCost', 
                  'sessions', 'createdAt']
        read_only_fields = ['id', 'patientId', 'createdAt']


#Create treatment plan serializer
class CreateTreatmentPlanSerializer(TreatmentPlanSerializer):
    class Meta(TreatmentPlanSerializer.Meta):
        fields = ['id', 'patientId', 'title', 'status', 'items', 'currency', 'totalCost', 
                  'sessions', 'createdAt']
        read_only_fields = ['id', 'patientId', 'createdAt']

    
    def validate(self, data):
        #validate total cost against treatment items
        items = data.get('treatment_items', [])
        totalCost = data.get('totalCost')
        total_from_prices = sum(float(item['price']) for item in items if items)
        total_from_prices = Decimal(str(total_from_prices))
        if (round(total_from_prices,2) != round(totalCost,2)
         or abs(total_from_prices - totalCost) > 0.01):
            logger.error(f'FRONTEND BUG: Total cost provided does not match treatment prices total! '
                         f'Total provided: {totalCost} - Total calculated: {total_from_prices}')
            data['totalCost'] = total_from_prices

        # #validate number of sessions
        # sessions_planned = data.get('sessions')
        # total_sessions = sum(float(item.get('session', 1)) for item in items if items)
        # if (sessions_planned and total_sessions) and sessions_planned < total_sessions:
        #     raise serializers.ValidationError({'sessions': _('Number of sessions cannot be lower than the total number of sessions for all treatment items.')})

        return data


    @transaction.atomic
    def create(self, validated_data):
        #Get request user 
        user = self.context.get('request').user

        #Assign doctor to validated data if user is 'dentist'
        if user.role == 'dentist':
            validated_data['doctor'] = user

        #Assign treatment to patient given the url patient ID 
        validated_data['patient_id'] = self.context.get('patient_id')  #uses foreign key for efficiency

        #Extract treatment items to handle their creation separately
        items_data = validated_data.pop('treatment_items', [])

        #Create treatment plan
        treatment_plan = TreatmentPlan.objects.create(**validated_data)

        #Bulk create treatment plan items 
        TreatmentPlanItem.objects.bulk_create([
            TreatmentPlanItem(
                treatmentPlan=treatment_plan,
                procedure=item['procedure'],
                procedureName=item['procedure'].name,
                toothNumber=item.get('toothNumber'),
                price=item['price'],
                session=item.get('session'),
                status=item.get('status', 'pending'),
                notes=item.get('notes')
            )
            for item in items_data
        ])

        return treatment_plan   #return created treatment plan instance


#Update treatment plan serializer 
class UpdateTreatmentPlanSerializer(TreatmentPlanSerializer):
    items = TreatmentPlanItemsSerializer(many=True, source='treatment_items', required=False, allow_empty=False)
    status = TranslatedChoiceField(choices=TreatmentPlan.TreatmentStatusChoices.choices,
                                   required=False, allow_blank=False, allow_null=False)

    class Meta(TreatmentPlanSerializer.Meta):
        fields = ['id', 'patientId', 'title', 'status', 'items', 'totalCost', 'sessions']
        read_only_fields = ['id', 'patientId']
        extra_kwargs = {field: {'required': False} for field in 
            ('title', 'status', 'items', 'totalCost', 'sessions')
            }

    def validate(self, data):
        #validate total cost against treatment items
        if 'treatment_items' in data:
            items = data.get('treatment_items', [])
            #re-calculate total cost if not provided
            totalCost_new = sum(float(item['price']) for item in items if items)
            totalCost_new = Decimal(str(totalCost_new))
            totalCost = data.get('totalCost', totalCost_new)
      
            if (round(totalCost_new,2) != round(totalCost,2)
             or abs(totalCost_new - totalCost) > 0.01):
                logger.error(f'FRONTEND BUG: Total cost provided does not match treatment prices total! '
                             f'Total provided: {totalCost} - Total calculated: {totalCost_new}')
            data['totalCost'] = totalCost_new

        #validate number of sessions
        # if 'sessions' in data:
        #     sessions_planned = data.get('sessions')
        #     total_sessions = sum(float(item.get('session', 1)) for item in items if items)
        #     if (sessions_planned and total_sessions) and sessions_planned < total_sessions:
        #         raise serializers.ValidationError({'sessions': _('Number of sessions cannot be lower than the total number of sessions for all treatment items.')})

        return data


    @transaction.atomic
    def update(self, instance, validated_data): 
        #fetch updated items (if any)
        updated_items = validated_data.pop('treatment_items', None)
        
        #delete and update items
        if updated_items is not None:  #or, use <<if 'treatment_items' in validated_data:>> if you want to allow deletion
            #delete existing items and recreate 
            instance.treatment_items.all().delete()

            #recreate treatment items from the data passed
            TreatmentPlanItem.objects.bulk_create(
              [
                TreatmentPlanItem(
                    treatmentPlan=instance,
                    procedure=item['procedure'],
                    procedureName=item['procedure'].name,
                    toothNumber=item.get('toothNumber'),
                    price=item['price'],
                    session=item.get('session'),
                    status=item.get('status', 'pending'),
                    notes=item.get('notes')
                )
                 for item in updated_items
              ]
            )

        
        #preserve old cost before updating for later checks
        totalCost_old = instance.totalCost
        
        #Update remaining fields
        for field, value in validated_data.items():
            setattr(instance, field, value)   #i.e. instance.field = value

        #Fetch installment plan for updates
        plan = getattr(instance, 'installment_plan', None)

        #Check if treatment cost changed to change installment plan's totalAmount accordingly
        totalCost_new = validated_data.get('totalCost')
        cost_changed = totalCost_new is not None and totalCost_new != totalCost_old
        if cost_changed and plan:
            cost_difference = round(totalCost_new - totalCost_old, 2)
            plan.totalAmount = Decimal(str(plan.totalAmount + cost_difference))
            #update installment plan's total
            plan_update_fields = ['totalAmount', 'updatedAt']
    
            #update amount per installment on the plan  #TODO -- move to a signal instead
            remaining_installments = plan.installments.filter(type='installment', paidAt__isnull=True)
            total_remaining = plan.totalAmount - (plan.totalPaid or Decimal('0')) #- (plan.downPayment or Decimal('0'))
            if remaining_installments:
                amount_per_installment = Decimal(str(total_remaining / len(remaining_installments)))
                remaining_installments.update(amount=amount_per_installment)
            else:
                if cost_difference > 0:
                    #add new installment with remaining
                    #update installment months
                    plan.installmentMonths = plan.installmentMonths+1
                    plan_update_fields.append('installmentMonths')
                    
                    #Create new installment with remaining amount
                    Installment.objects.create(
                        installmentPlan=plan,
                        amount=total_remaining,
                        sequence=(plan.installmentMonths+1),
                        dueDate=timezone.localdate(timezone.now()),
                        type='installment'
                    )
            
            #update installment plan
            plan.save(update_fields=plan_update_fields)

        #update treatment instance
        instance.save(update_fields=list(validated_data.keys()))
        
        #update the amount on the associated bill too -- let the bill update after the treatment
        if cost_changed:
            if plan and plan.active_bill:
                plan.active_bill.totalAmount = plan.totalAmount
                plan.active_bill.save(update_fields=['totalAmount', 'treatmentTitle', 'procedures', 'updatedAt'])
            else:
                treatment_bill = instance.treatment_bills.filter(treatment_id=instance.id).first()
                if treatment_bill:
                    treatment_bill.totalAmount = instance.totalAmount
                    treatment_bill.save(update_fields=['totalAmount', 'treatmentTitle', 'procedures', 'updatedAt'])

        return instance


#Treatment plans options serializer
@treatmentplans_options_schema
class TreatmentPlanOptionsSerializer(serializers.Serializer):
    treatmentStatusChoices = serializers.SerializerMethodField()
    procedureChoices = serializers.SerializerMethodField()
    validToothNumbers = serializers.SerializerMethodField()
    itemStatusChoices = serializers.SerializerMethodField()
    installmentMonthsChoices = serializers.SerializerMethodField()
    installmentPlanStatusChoices = serializers.SerializerMethodField()
    installmentStatusChoices = serializers.SerializerMethodField()

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_treatmentStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in TreatmentPlan.TreatmentStatusChoices
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
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_validToothNumbers(self, obj):
        return [
            {'value': tooth[0], 'label': tooth[1]}
             for tooth in TEETH_CHOICES
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_itemStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in TreatmentPlanItem.ItemStatusChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_installmentMonthsChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in InstallmentPlan.InstallmentMonthsChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_installmentPlanStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in InstallmentPlan.InstallmentPlanStatusChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_installmentStatusChoices (self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Installment.InstallmentStatusChoices
        ]
