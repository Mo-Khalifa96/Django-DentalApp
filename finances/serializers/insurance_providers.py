from clinic.models import Branch
from rest_framework import serializers
from finances.models import InsuranceProvider
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from finances.docs import insurance_providers_options_schema


#INSURANCE PROVIDERS SERIALIZERS
#Insurance provider serializer -- base serializer
class InsuranceProviderSerializer(ValidateBranchMixin, serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    tier = TranslatedChoiceField(choices=InsuranceProvider.InuranceTierChoices.choices, required=True)

    class Meta:
        model = InsuranceProvider
        fields = ['id', 'name', 'fullName', 'tier', 'contact', 'coveragePercent',
            'annualMax', 'deductible', 'currency', 'responseDays', 'color', 'branchId', 'notes']
        read_only_fields = ['id']
        extra_kwargs = {'contact': {'required': True, 'allow_null': False, 'allow_blank': False}}


#Retrieve/update/delete insurance provider serializer
class RetrieveUpdateDeleteInsuranceProviderSerializer(UserPermissionsMixin, InsuranceProviderSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    tier = TranslatedChoiceField(choices=InsuranceProvider.InuranceTierChoices.choices, required=False)
    
    class Meta(InsuranceProviderSerializer.Meta):
        fields = ['id', 'name', 'fullName', 'tier', 'contact', 'coveragePercent',
            'annualMax', 'deductible', 'currency', 'responseDays', 'color', 'branchId', 'notes']
        read_only_fields = ['id', 'branchId']
        extra_kwargs = {'contact': {'allow_null': False, 'allow_blank': False}}



#Insurance providers options serializer
@insurance_providers_options_schema
class InsuranceProvidersOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    tierChoices = serializers.SerializerMethodField()

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
    def get_tierChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in InsuranceProvider.InuranceTierChoices
        ]


#Other
#Create new provider serializer -- nested serializer
class CreateNewProviderSerializer(InsuranceProviderSerializer):
    class Meta(InsuranceProviderSerializer.Meta):
        fields = ['id', 'name', 'tier', 'coveragePercent', 'annualMax', 'deductible', 'currency', 'notes']
        read_only_fields = ['id']
        extra_kwargs = {field: {'required': False, 'allow_null': True} for field in
            ('coveragePercent', 'annualMax', 'deductible', 'currency', 'notes')
        }
    
    def validate(self, data):
        data.setdefault('coveragePercent', 0)
        data.setdefault('annualMax', None)
        data.setdefault('deductible', None)
        data.setdefault('currency', None)
        data.setdefault('notes', None)
        return data
