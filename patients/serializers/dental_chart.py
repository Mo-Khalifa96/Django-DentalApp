from django.db import transaction
from rest_framework import serializers
from patients.models import DentalChart
from patients.validators import FDI_PERMANENT
from utils.swagger_utils import extend_schema_field
from patients.docs import dentalchart_options_schema
from django.utils.translation import gettext_lazy as _



#SERIALIZERS FOR PATIENT DENTAL CHARTS
#Tooth serializer -- nested (dict) serializer
class ToothDetailSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DentalChart.ToothStatusChoices.choices)
    surfaces = serializers.ListField(child=serializers.ChoiceField(
         choices=DentalChart.ToothSurfacesChoices.choices
    ), required=False, allow_empty=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if not request:
            return 
        if request.method == 'PUT':
            self.fields['status'].required = True
        else:
            self.fields['status'].required = False


#Dental Chart serializer
class DentalChartSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    teeth = serializers.DictField(child=ToothDetailSerializer(many=False))
    
    class Meta:
        model = DentalChart
        fields = ['patientId', 'teeth', 'lastUpdated']
        read_only_fields = ['patientId', 'lastUpdated']


    def validate_teeth(self, teeth):
        #get stored teeth dictionary  
        teeth_before = self.instance.teeth

        #Validate incoming data based on method
        req_method = self.context.get('request').method
        if (req_method == 'PUT') and (len(teeth.keys()) < len(teeth_before.keys())):
            raise serializers.ValidationError(_('Teeth data missing or incomplete.'))
        elif (req_method == 'PATCH') and not teeth:
            raise serializers.ValidationError(_('Teeth data required for update.'))

        errors = {}
        for tooth_number in teeth:
            if tooth_number not in FDI_PERMANENT:
                errors[tooth_number] = _('Invalid FDI tooth number.')
                continue
        if errors:  #return errors (if any)
            raise serializers.ValidationError(errors)

        return teeth
    
    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get('request')

        #fetch updated teeth from validated data 
        updated_teeth = validated_data.get('teeth', {})

        if request.method == 'PATCH':
            #get and use stored teeth dict for patch update
            teeth_dict = instance.teeth.copy()
            for tooth_number, tooth_data in updated_teeth.items():
                #merge at the field level within each touched tooth,
                existing_tooth = teeth_dict.get(tooth_number, {})
                teeth_dict[tooth_number] = {**existing_tooth, **tooth_data}
            instance.teeth = teeth_dict
        
        else:
            #update entire teeth dict
            instance.teeth = updated_teeth

        instance.save(update_fields=['teeth', 'lastUpdated'])
        return instance


#Serializer for providing dental chart options
@dentalchart_options_schema 
class DentalChartOptionsSerializer(serializers.Serializer):
    toothNumberChoices = serializers.SerializerMethodField()
    toothStatusChoices = serializers.SerializerMethodField()
    toothSurfaceChoices = serializers.SerializerMethodField()

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_toothNumberChoices(self, obj):
        return [
            {'value': tooth[0], 'label': tooth[1]}
             for tooth in [(n, n) for n in sorted(FDI_PERMANENT)]
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_toothStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in DentalChart.ToothStatusChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_toothSurfaceChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in DentalChart.ToothSurfacesChoices
        ]
