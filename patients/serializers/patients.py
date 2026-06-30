from clinic.models import Branch
from django.db import transaction
from rest_framework import serializers
from patients.validators import FDI_PERMANENT
from finances.models import InsuranceProvider
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
class CreatePatientSerializer(ValidateBranchMixin, serializers.ModelSerializer):
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    insurance = serializers.CharField(source='patient_insurance.providerName', default=None, read_only=True)
    insuranceProviderId = serializers.PrimaryKeyRelatedField(queryset=InsuranceProvider.objects.all(),
                                        required=False, default=None, allow_null=True, write_only=True)
    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId',
                  'bloodType', 'allergies', 'insurance', 'insuranceProviderId', 'notes', 'status', 
                  'branchId', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'status', 'insurance', 'createdAt', 'updatedAt']
    
    def validate_countryCode(self, countryCode):
        if not countryCode:
            raise serializers.ValidationError(_('Country code is required.'))
        code_cleaned = countryCode.lstrip('+').lstrip('0')
        if (not code_cleaned.isnumeric()) or len(code_cleaned) > 5:
            raise serializers.ValidationError(_('Country code entered is invalid. Please enter a valid number.'))
        return countryCode

    def to_representation(self, instance):
        data = super().to_representation(instance)
        phone = data.get('phone')
        code = data.get('countryCode')
        if phone and code:
            try:
                data['phone'] = '0' + phone[len(code):]
            except:
                data['phone'] = phone 
        return data

    @transaction.atomic
    def create(self, validated_data):
        provider = validated_data.pop('insuranceProviderId', None)
        patient = Patient.objects.create(**validated_data)
        patient.save(provider=provider)
        return patient


#Serializer for patient listing 
class ListPatientSerializer(serializers.ModelSerializer): 
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    insurance = serializers.CharField(source='patient_insurance.providerName', read_only=True)
    insuranceId = serializers.CharField(source='patient_insurance.memberId', read_only=True)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'phone', 'email', 'address', 'nationalId', 'bloodType', 
                  'allergies', 'insurance', 'insuranceId', 'lastVisit', 'nextAppointment', 'notes', 
                  'status', 'branchId', 'createdAt', 'updatedAt']
    

#Serializer for retrieving patient details 
class RetrievePatientSerializer(UserPermissionsMixin, serializers.ModelSerializer): 
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    insurance = serializers.CharField(source='patient_insurance.providerName', read_only=True)
    insuranceId = serializers.CharField(source='patient_insurance.memberId', read_only=True)
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
    insurance = serializers.CharField(source='patient_insurance.providerName', default=None, read_only=True)
    insuranceProviderId = serializers.PrimaryKeyRelatedField(queryset=InsuranceProvider.objects.all(), 
                                                        required=False, allow_null=True, write_only=True)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'countryCode', 'phone', 'address', 'nationalId', 'bloodType', 
                  'allergies', 'insurance', 'insuranceProviderId', 'notes', 'status', 'updatedAt']
        read_only_fields = ['id', 'name', 'insurance', 'updatedAt']
        extra_kwargs = {field: {'required': False} for field in 
            ('name', 'countryCode', 'phone', 'address', 'nationalId', 'bloodType', 'allergies',
            'insuranceProviderId', 'notes', 'status')
            }
    
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     request = self.context.get('request')
    #     is_put_request = request and request.method == 'PUT'
    #     self.fields['insuranceProviderId'].required = True if is_put_request else False

    def validate(self, data):
        code, phone = data.get('countryCode'), data.get('phone')
        if (phone and not code) or (code and not phone):
            raise serializers.ValidationError({'phone': _('Both country code and phone are required to update.')})
        return data 

    def to_representation(self, instance):
        data = super().to_representation(instance)
        phone = data.get('phone')
        code = data.get('countryCode')
        if phone and code:
            try:
                data['phone'] = '0' + phone[len(code):]
            except:
                data['phone'] = phone 
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        #create object to flag missing provider
        _MISSING = object()

        #handle patient's insurance coverage upon provider update
        insurance_provider = validated_data.pop('insuranceProviderId', _MISSING)
        if insurance_provider is not _MISSING and\
         insurance_provider != instance.patient_insurance.provider:
            #get patient inurance coverage instance
            coverage = instance.patient_insurance

            #assign new provider
            coverage.provider = insurance_provider

            #set old fields to None
            for field in ('memberId', 'annualMax', 'deductibleMet', 'usedYTD', 'currency',
                        'effectiveFrom', 'effectiveTo', 'eligibilityChecked', 'eligibilityStatus'):
                setattr(coverage, field, None)
            
            #save patient coverage changes
            coverage.save()

        #call parent update() method
        return super().update(instance, validated_data)


#Serializer for providing procedure options
@patients_options_schema 
class PatientsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    insuranceProviderChoices = serializers.SerializerMethodField()
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
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_insuranceProviderChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId} if branchId else {}
        return [
                {'providerId': branch_id, 'name': name} 
                    for branch_id,name in InsuranceProvider.objects.filter(**filters)\
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
class NewPatientSerializer(serializers.ModelSerializer):
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'createdAt']
        read_only_fields = ['id', 'createdAt']
