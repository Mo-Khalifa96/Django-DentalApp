from clinic.models import Branch
from django.db import transaction
from rest_framework import serializers
from patients.validators import FDI_PERMANENT
from patients.models import Patient, DentalChart
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from services.translation.serializers import TranslatedChoiceField
from patients.docs import (create_patient_schema, update_patient_schema, patients_options_schema, 
                            dentalchart_options_schema)


#SERIALIZERS FOR PATIENTS
#Serializer for creating new patient
@create_patient_schema
class CreatePatientSerializer(serializers.ModelSerializer, ValidateBranchMixin):
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(),
                                                  required=False, allow_null=True)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId',
                  'bloodType', 'allergies', 'insurance', 'insuranceId', 'notes', 'status', 'branchId', 
                  'createdAt', 'updatedAt']
        read_only_fields = ['id', 'status', 'createdAt', 'updatedAt']
        extra_kwargs = {field: {'required': False} for field in
                ('email', 'address', 'bloodType', 'nationalId', 'allergies', 'insurance',
                 'insuranceId', 'notes', 'branchId')
            }
    
    def validate_countryCode(self, countryCode):
        if not countryCode:
            raise serializers.ValidationError(_('Country code is required.'))
        if (not countryCode.isnumeric()) or len(countryCode) > 5:
            raise serializers.ValidationError(_('Country code entered is invalid. Please enter a valid number.'))
        return countryCode

    def to_representation(self, instance):
        data = super().to_representation(instance)
        phone, code = data.get('phone'), data.get('countryCode')
        if phone and code:
            try:
                data['phone'] = '0' + phone[len(code):]
            except:
                data['phone'] = phone 
        return data


#Serializer for patient listing 
class ListPatientSerializer(serializers.ModelSerializer): 
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    phone = serializers.SerializerMethodField()  

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'phone', 'email', 'address', 'nationalId', 'bloodType', 
                  'allergies', 'insurance', 'insuranceId', 'lastVisit', 'nextAppointment', 'notes', 
                  'status', 'branchId', 'createdAt', 'updatedAt']
    
    @extend_schema_field(serializers.CharField)
    def get_phone(self, obj):  #NOTE - use try/except in case of problems
        return str(obj.phone).replace('00', '+', 1) if obj.phone.startswith('00') else obj.phone
        #or,  '0' + obj.phone[len(obj.countryCode):]


#Serializer for retrieving patient details 
class RetrievePatientSerializer(UserPermissionsMixin, serializers.ModelSerializer): 
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    phone = serializers.SerializerMethodField()  

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId',
                  'bloodType', 'allergies', 'insurance', 'insuranceId', 'lastVisit', 'nextAppointment', 
                  'notes', 'status', 'branchId', 'createdAt', 'updatedAt']
    
    @extend_schema_field(serializers.CharField)
    def get_phone(self, obj):
        return '0' + obj.phone[len(obj.countryCode):]


#Serializer for updating patient details 
@update_patient_schema
class UpdatePatientSerializer(serializers.ModelSerializer):
    status = TranslatedChoiceField(choices=Patient.StatusChoices.choices, required=False)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'countryCode', 'phone', 'address', 'nationalId', 'bloodType', 
                  'allergies', 'insurance', 'insuranceId', 'notes', 'status', 'updatedAt']
        read_only_fields = ['id', 'name', 'updatedAt']
        extra_kwargs = {field: {'required': False} for field in 
            ('name', 'countryCode', 'phone', 'address', 'nationalId', 'bloodType', 'allergies', 'insurance',
            'insuranceId', 'notes', 'status')
            }
        
    def validate(self, data):
        code, phone = data.get('countryCode'), data.get('phone')
        if (phone and not code) or (code and not phone):
            raise serializers.ValidationError({'phone': _('Both country code and phone are required to update.')})
        return data 

    def to_representation(self, instance):
        data = super().to_representation(instance)
        phone, code = data.get('phone'), data.get('countryCode')
        if phone and code:
            try:
                data['phone'] = '0' + phone[len(code):]
            except:
                data['phone'] = phone 
        return data


#Serializer for providing procedure options
@patients_options_schema 
class PatientsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    genderChoices = serializers.SerializerMethodField()
    statusChoices = serializers.SerializerMethodField()
    bloodTypeChoices = serializers.SerializerMethodField()

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
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_genderChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Patient.GenderChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_statusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Patient.StatusChoices
        ]
    
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_bloodTypeChoices(self, obj):
        return [
            {'value': choice[0], 'label': choice[1]}
            for choice in Patient.bloodTypeChoices
        ]


##########################


#SERIALIZERS FOR PATIENT DENTAL CHARTS
#Tooth serializer
class ToothDetailSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DentalChart.ToothStatusChoices.choices)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

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

        #Validate incoming data 
        if not isinstance(teeth, dict):
            raise serializers.ValidationError(_('Invalid data format.'))
        if (self.context['request'].method == 'PUT') and (len(teeth.keys()) < len(teeth_before.keys())):
            raise serializers.ValidationError(_('Teeth data missing or incomplete.'))
        elif (self.context['request'].method == 'PATCH') and not teeth:
            raise serializers.ValidationError(_('Teeth data required for update.'))

        errors, validated = {}, {}
        for tooth_number, tooth_dict in teeth.items():
            if tooth_number not in FDI_PERMANENT:
                errors[tooth_number] = f'Invalid FDI tooth number.'
                continue

            #Validate inner structure
            inner_serializer = ToothDetailSerializer(data=tooth_dict)
            if inner_serializer.is_valid():
                #store valid tooth data 
                validated[tooth_number] = inner_serializer.validated_data
            else:
                errors[tooth_number] = inner_serializer.errors
        
        if errors:  #return errors (if any)
            raise serializers.ValidationError(errors)

        return validated
    
    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get('request')

        #fetch updated teeth from validated data 
        updated_teeth = validated_data.get('teeth', {})

        if request.method == 'PATCH':
            #get and use stored teeth dict for update
            teeth_dict = instance.teeth.copy()
            teeth_dict.update(updated_teeth)
            instance.teeth = teeth_dict
        else:
            #update entire teeth dict
            instance.teeth = updated_teeth

        instance.save(update_fields=['teeth', 'lastUpdated'])
        return instance


#Serializers for providing dental chart options
@dentalchart_options_schema 
class DentalChartOptionsSerializer(serializers.Serializer):
    toothNumberChoices = serializers.SerializerMethodField()
    toothStatusChoices = serializers.SerializerMethodField()

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


##########################


#Other
#Serializer for creating new patient upon creating new appointment
class NewPatientSerializer(serializers.ModelSerializer, ValidateBranchMixin):
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(),
                                                required=False, allow_null=True)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'branchId', 'createdAt']
        read_only_fields = ['id', 'createdAt']

