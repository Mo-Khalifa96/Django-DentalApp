from rest_framework import serializers
from utils.mixins import ValidateBranchMixin
from clinic.models import Branch, SterilizationLog
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from clinic.docs import sterilization_logs_options_schema
from services.translation.serializers import TranslatedChoiceField


#Valid choices for instrument sets -- for validation
valid_instrumentSet_choices = {instrument_set[0] for instrument_set in SterilizationLog.InstrumentSetsChoices.choices}


#SERIALIZERS FOR STERILIZATION LOGS 
#Sterilization logs serializer -- base serializer
class SterilizationLogSerializer(serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    result = TranslatedChoiceField(
            choices=SterilizationLog.SterilizationResultChoices.choices, allow_blank=True, allow_null=True
        )
   
    class Meta:
        model = SterilizationLog
        fields = ['id', 'date', 'time', 'cycleType', 'instrumentSets', 'operator', 'result', 
                  'sealedAt', 'shelfLifeDays', 'notes', 'branchId', 'createdAt', 'updatedAt']


#Create sterilization log serializer 
class CreateSterilizationLogSerializer(SterilizationLogSerializer, ValidateBranchMixin):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta(SterilizationLogSerializer.Meta):
        fields = ['id', 'date', 'time', 'cycleType', 'instrumentSets', 'operator', 'result', 'sealedAt',
                  'shelfLifeDays', 'notes', 'branchId', 'createdAt']
        read_only_fields = ['id', 'date', 'time', 'createdAt']


    def validate_operator(self, operator):
        if not operator:
            user = self.context.get('request').user
            operator = user.name
        return operator
    
    def validate_instrumentSets(self, sets):
        if not sets:
            raise serializers.ValidationError(_('At least one instrument set is required.'))
        
        sets = sorted(list(set(sets)))

        errors = []
        for instrument_set in sets:
            if instrument_set not in valid_instrumentSet_choices:
                errors.append(_(f'{instrument_set} is not a valid instrument set choice.'))
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return sets


#Update sterilization logs serializer
class UpdateSterilizationLogSerializer(SterilizationLogSerializer):
    result = TranslatedChoiceField(
            choices=SterilizationLog.SterilizationResultChoices.choices, required=False, allow_blank=True, allow_null=True
        )
   
    class Meta(SterilizationLogSerializer.Meta):
        fields = ['id', 'date', 'time', 'cycleType', 'instrumentSets', 'operator', 'result', 
                  'sealedAt', 'shelfLifeDays', 'notes', 'branchId', 'updatedAt']
        read_only_fields = ['id', 'date', 'time', 'branchId', 'updatedAt']


#Sterilization logs options serializer
@sterilization_logs_options_schema
class SterilizationLogsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    cycleTypeChoices = serializers.SerializerMethodField()
    instrumentSetsChoices = serializers.SerializerMethodField()
    resultChoices = serializers.SerializerMethodField()

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
    def get_cycleTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in SterilizationLog.CycleTypeChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_instrumentSetsChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in SterilizationLog.InstrumentSetsChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_resultChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in SterilizationLog.SterilizationResultChoices
        ]


