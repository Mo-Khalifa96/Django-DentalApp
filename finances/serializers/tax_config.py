from clinic.models import Branch
from rest_framework import serializers
from utils.mixins import UserPermissionsMixin
from finances.models import ClinicalTaxConfig
from django.utils.translation import gettext_lazy as _

#TODO - have to use a queryparam for branch
#Tax clinic configurations serializer -- base serializer for retrieval and update
class TaxConfigSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)

    class Meta:
        model = ClinicalTaxConfig
        fields = ['id', 'clinicName', 'address', 'phone', 'taxId', 'activityCode', 
                  'commercialReg', 'branchId']
        read_only_fields = ['id', 'branchId']


#TODO - have to use a queryparam for branch
#Create clinic tax configurations serializer    
class CreateTaxConfigSerializer(TaxConfigSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta(TaxConfigSerializer.Meta):
        fields = ['id', 'clinicName', 'address', 'phone', 'taxId', 'activityCode', 
                  'commercialReg', 'branchId']
        read_only_fields = ['id']

    def validate_branchId(self, branch):
        if not branch:
            branch = self.context.get('branch', None)  #Passed from serializer
        return branch

    # def validate_branchId(self, branch):
    #     if not branch:
    #         user = self.context['request'].user
    #         if user.branch:
    #             return user.branch
    #     return branch
