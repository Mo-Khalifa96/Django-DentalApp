from rest_framework import serializers
from clinic.models import Branch, Procedure
from clinic.docs import procedures_options_schema
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin


#SERIALIZERS FOR PROCEDURES
#General-purpose procedures serializer
class ProcedureSerializer(UserPermissionsMixin, ValidateBranchMixin, serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Procedure
        fields = ['id', 'name', 'category', 'duration', 'currency', 'price', 'description', 'branchId', 'createdAt']
        read_only_fields = ['id', 'createdAt']


#Procedure serializer subclass for put/patch requests
class UpdateProcedureSerializer(ProcedureSerializer):
    class Meta:
        model = Procedure
        fields = ['id', 'name', 'category', 'duration', 'currency', 'price', 'description', 'createdAt']
        read_only_fields = ['id', 'createdAt']
        extra_kwargs = {field: {'required': False} for field in 
            ('name', 'category', 'duration', 'currency', 'price', 'description')
            }


#Serializer for serving choice options for procedure creation
@procedures_options_schema
class ProceduresOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    categoryChoices = serializers.SerializerMethodField()

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_branchChoices(self, obj):
        return [
            {'branchId': branch_id, 'name': name} 
                for branch_id,name in Branch.objects\
                .values_list('id', 'name').order_by('-isMain', 'name')
            ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_categoryChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in Procedure.ProcedureCategory
        ]
