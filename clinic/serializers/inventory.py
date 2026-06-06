from rest_framework import serializers
from clinic.models import Branch, Inventory
from clinic.docs import inventory_options_schema
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin


#SERIALIZERS FOR INVENTORY
#General purpose inventory serializer 
class InventorySerializer(UserPermissionsMixin, serializers.ModelSerializer):
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Inventory
        fields = ['id', 'name', 'category', 'currentStock', 'minStock', 'unit', 
                  'supplier', 'lastOrdered', 'branchId', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'branchId', 'createdAt', 'updatedAt']


#Create inventory items serializer
class CreateInventoryItemSerializer(InventorySerializer, ValidateBranchMixin):
    class Meta(InventorySerializer.Meta):
        fields = ['id', 'name', 'category', 'currentStock', 'minStock', 'unit', 
                  'supplier', 'lastOrdered', 'branchId', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'lastOrdered', 'createdAt', 'updatedAt']


#Update inventory serializer 
class UpdateInventorySerializer(InventorySerializer):
    class Meta(InventorySerializer.Meta):
        fields = ['id', 'name', 'category', 'currentStock', 'minStock', 'unit', 
                  'supplier', 'lastOrdered', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'createdAt', 'updatedAt']
        extra_kwargs = {field: {'required': False} for field in 
            ('name', 'category', 'currentStock', 'minStock', 'unit', 'supplier', 'lastOrdered')
            }


#Serializer for serving choice options for inventory creation
@inventory_options_schema
class InventoryOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    categoryChoices = serializers.SerializerMethodField()
    unitChoices = serializers.SerializerMethodField()

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
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId} if branchId else {}  #in case n_branches == 0
        return [
            {'value': category, 'label': category}
             for category in Inventory.objects.filter(**filters)\
              .values_list('category', flat=True).distinct().order_by('category')
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_unitChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []

        filters = {'branch_id': branchId} if branchId else {}  #in case n_branches == 0
        return [
            {'value': unit, 'label': unit}
             for unit in Inventory.objects.filter(**filters)\
              .values_list('unit', flat=True).distinct().order_by('unit')
        ]
