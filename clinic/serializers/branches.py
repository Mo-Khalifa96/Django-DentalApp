from clinic.models import Branch
from rest_framework import serializers
from clinic.models import WorkingDaysLookUp
from clinic.docs import branch_options_schema
from utils.mixins import UserPermissionsMixin
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField


#BRANCH SERIALIZERS 
#Base branch serializer
class BranchSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    workingDays = serializers.ListField(child=TranslatedChoiceField(choices=WorkingDaysLookUp.choices))

    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'phone', 'workingDays', 'openTime', 'closeTime',
                  'color', 'createdAt']
        read_only_fields = ['id', 'createdAt']
    
    def validate_workingDays(self, value):
        if value:
            #remove duplicates (if any)
            value = sorted(set(value))
        return value


#Create branch serializer
class CreateBranchSerializer(BranchSerializer):    
    class Meta(BranchSerializer.Meta):
        fields = ['id', 'name', 'address', 'phone', 'workingDays', 'openTime', 'closeTime',
                  'rooms', 'isMain', 'color', 'createdAt']
        read_only_fields = ['id', 'createdAt']


#Update branch serializer
class UpdateBranchSerializer(BranchSerializer):
    workingDays = serializers.ListField(
        child=TranslatedChoiceField(choices=WorkingDaysLookUp.choices),
         required=False)

    class Meta(BranchSerializer.Meta):
        fields = ['id', 'name', 'address', 'phone', 'workingDays', 'openTime', 'closeTime',
                  'rooms', 'isMain', 'color', 'createdAt']
        read_only_fields = ['id', 'createdAt']
        extra_kwargs = {field: {'required': False} for field in
            ('name', 'address', 'phone', 'openTime', 'closeTime', 'rooms', 'isMain', 'color')
        }


#Serializer for serving choice options for branch creation
@branch_options_schema
class BranchOptionsSerializer(serializers.Serializer):
    weekDaysChoices = serializers.SerializerMethodField()

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_weekDaysChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in WorkingDaysLookUp
        ]

