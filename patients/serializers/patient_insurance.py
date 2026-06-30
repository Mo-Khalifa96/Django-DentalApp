from django.db import transaction
from clinic.models import Branch
from patients.models import Patient
from rest_framework import serializers
from patients.models import PatientCoverage
from finances.models import InsuranceProvider
from utils.mixins import UserPermissionsMixin
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField
from finances.serializers.insurance_providers import CreateNewProviderSerializer
from patients.docs import patient_insurance_options_schema


#Reference object to patient coverage fields
COVERAGE_FIELDS = ('provider', 'providerName', 'memberId', 'annualMax', 'usedYTD', 'deductibleMet',
                   'currency', 'effectiveFrom', 'effectiveTo', 'eligibilityChecked', 'eligibilityStatus')


#PATIENT INSURANCE COVERAGE SERIALIZERS 
#List patient insurance coverages serializer
class ListPatientCoverageSerializer(serializers.ModelSerializer):
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    patientName = serializers.CharField(source='patient.name', read_only=True)
    providerId = serializers.PrimaryKeyRelatedField(source='provider', read_only=True)
    eligibilityStatus = TranslatedChoiceField(choices=PatientCoverage.EligibilityStatusChoices.choices, read_only=True)

    class Meta:
        model = PatientCoverage
        fields = ['id', 'patientId', 'patientName', 'providerId', 'providerName', 'memberId', 
                  'annualMax', 'deductibleMet', 'usedYTD', 'effectiveFrom', 'effectiveTo', 
                  'eligibilityChecked', 'eligibilityStatus', 'updatedAt']


#Create patient insurance coverage serializer
class CreatePatientCoverageSerializer(serializers.ModelSerializer):
    patientName = serializers.CharField(source='patient.name', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    providerId = serializers.PrimaryKeyRelatedField(source='provider', queryset=InsuranceProvider.objects.all(), required=False, allow_null=True)
    is_newProvider = serializers.BooleanField(required=False, allow_null=True, write_only=True)
    newProviderDetails = CreateNewProviderSerializer(many=False, required=False, allow_null=True, write_only=True)
    eligibilityStatus = TranslatedChoiceField(choices=PatientCoverage.EligibilityStatusChoices.choices, required=True, allow_null=True)

    class Meta:
        model = PatientCoverage
        fields = ['id', 'patientName', 'patientId', 'providerName', 'providerId', 'is_newProvider', 
                  'newProviderDetails', 'memberId', 'annualMax', 'usedYTD', 'deductibleMet', 'currency',
                  'effectiveFrom', 'effectiveTo', 'eligibilityChecked', 'eligibilityStatus']
        read_only_fields = ['id', 'patientName', 'patientId', 'providerName']
        extra_kwargs = {
            'memberId': {'required': True, 'allow_null': False, 'allow_blank': False},
            'deductibleMet': {'required': False, 'default': False},
            **{field: {'required': True} for field in ('annualMax', 'effectiveFrom', 'effectiveTo', 'eligibilityStatus')},
            **{field: {'required': False} for field in (
               'providerId', 'is_newProvider', 'newProviderDetails', 'usedYTD', 'currency', 'eligibilityChecked'
               )
            }
        }

    #validate insurer-related data
    def validate(self, data):
        provider = data.get('provider')
        coverage = self.context.get('coverage')
        is_new_provider = data.get('is_newProvider', False)
        new_provider_details = data.get('newProviderDetails')

        if is_new_provider:
            if not new_provider_details:
                raise serializers.ValidationError({'newProviderDetails': _('New insurance provider details required if creating a new provider')})
            if provider:
                raise serializers.ValidationError({'providerId': _('Cannot assign an existing insurance provider if choosing to create a new one.')})
        else:
            if not provider:
                if new_provider_details:
                    data['is_newProvider'] = True 

                    #try to identify current branch for new the provider
                    user = self.context.get('request').user
                    if user.branches.count() == 1:
                        data['branch'] = user.branches.first()
                    elif getattr(coverage.patient, 'branch_id', None):
                        data['branch'] = coverage.patient.branch
                    elif getattr(user, 'branch_id', None):
                        data['branch'] = user.branch
                    elif Branch.objects.exists() and user.branches.exists():
                        data['branch'] = user.branches.first()
                
                else:
                    raise serializers.ValidationError({'providerId': _('An insurance provider is required to create a new insurance plan.')})
        
        #anticipate insurance provider change
        if new_provider_details or provider:
            for field in COVERAGE_FIELDS:
                setattr(coverage, field, None)
                # coverage.save()
        
        #assign coverage instance to data
        data['coverage'] = coverage

        #return validated data
        return data

    @transaction.atomic
    def create(self, validated_data):
        is_new_provider = validated_data.pop('is_newProvider', False)
        new_provider_details = validated_data.pop('newProviderDetails', None)
        branch = validated_data.pop('branch', None)
        coverage = validated_data.pop('coverage')

        if is_new_provider and new_provider_details:
            provider = InsuranceProvider.objects.create(**new_provider_details,
                                                  branch=(branch if branch else None))

            #override provider object to assign the new provider
            validated_data['provider'] = provider
        
        
        #update with the validated data
        for field, value in validated_data.items():
            setattr(coverage, field, value)  #i.e. coverage.field = value
        
        #update coverage instance and return
        coverage.save()
        return coverage
        

#Retrieve/update patient insurance coverage serializer
class RetrieveUpdatePatientCoverageSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    patientName = serializers.CharField(source='patient.name', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    providerId = serializers.PrimaryKeyRelatedField(source='provider', queryset=InsuranceProvider.objects.all(), required=False, allow_null=True)
    is_newProvider = serializers.BooleanField(required=False, allow_null=True, write_only=True)
    newProviderDetails = CreateNewProviderSerializer(many=False, required=False, allow_null=True, write_only=True)
    eligibilityStatus = TranslatedChoiceField(choices=PatientCoverage.EligibilityStatusChoices.choices, required=False, allow_null=True)

    class Meta:
        model = PatientCoverage
        fields = ['id', 'patientName', 'patientId', 'providerName', 'providerId', 'is_newProvider', 
                  'newProviderDetails', 'memberId', 'annualMax', 'usedYTD', 'deductibleMet', 'currency',
                  'effectiveFrom', 'effectiveTo', 'eligibilityChecked', 'eligibilityStatus', 'updatedAt']
        read_only_fields = ['id', 'patientName', 'patientId', 'providerName', 'updatedAt']
        extra_kwargs = {
            'memberId': {'allow_null': False, 'allow_blank': False},
            'deductibleMet': {'required': False, 'default': False},
            **{field: {'required': False} for field in (
               'providerId', 'is_newProvider', 'newProviderDetails', 'usedYTD', 'currency', 'eligibilityChecked'
               )
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if not request:
            return 
        if request.method == 'PUT':
            self.fields['memberId'].required = True
            self.fields['annualMax'].required = True
            self.fields['effectiveFrom'].required = True
            self.fields['effectiveTo'].required = True
            self.fields['eligibilityStatus'].required = True
        else:
            self.fields['memberId'].required = False
            self.fields['annualMax'].required = False
            self.fields['effectiveFrom'].required = False
            self.fields['effectiveTo'].required = False
            self.fields['eligibilityStatus'].required = False
            

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if request.method == 'GET':
            if (instance.patient and instance.updatedAt and
             instance.updatedAt.date() == instance.patient.createdAt.date()):
                rep['updatedAt'] = None
        return rep

    #validate insurer-related data
    def validate(self, data):
        if all([field not in data.keys() for field in ('provider', 'is_newProvider', 'newProviderDetails')]):
            return data 

        coverage = self.instance
        current_provider = data.get('provider') #or self.instance.provider
        is_new_provider = data.get('is_newProvider', False)
        new_provider_details = data.get('newProviderDetails')

        if is_new_provider:
            if not new_provider_details:
                raise serializers.ValidationError({'newProviderDetails': _('New insurance provider details required if creating a new provider')})
            if current_provider:
                raise serializers.ValidationError({'providerId': _('Cannot assign an existing insurance provider if choosing to create a new one.')})
        else:
            if not current_provider:
                if new_provider_details:
                    data['is_newProvider'] = True
    
                    #try to identify current branch for new the provider
                    user = self.context.get('request').user
                    if user.branches.count() == 1:
                        data['branch'] = user.branches.first()
                    elif getattr(coverage.patient, 'branch_id', None):
                        data['branch'] = coverage.patient.branch
                    elif getattr(user, 'branch_id', None):
                        data['branch'] = user.branch
                    elif Branch.objects.exists() and user.branches.exists():
                        data['branch'] = user.branches.first()
                
                elif 'provider' in data:
                    #if removing insurance coverage -- set field values to None
                    for field in COVERAGE_FIELDS:
                        data[field] = None
        
        #anticipate insurance provider change
        if new_provider_details or (current_provider and current_provider != self.instance.provider):
            for field in COVERAGE_FIELDS:
                setattr(self.instance, field, None)
        
        #return validated data
        return data

    @transaction.atomic 
    def update(self, instance, validated_data):
        is_new_provider = validated_data.pop('is_newProvider', False)
        new_provider_details = validated_data.pop('newProviderDetails', None)
        branch = validated_data.pop('branch', None)

        #handle new insurance provider
        if is_new_provider and new_provider_details:
            provider = InsuranceProvider.objects.create(**new_provider_details,
                                                  branch=(branch if branch else None))

            #add new provider object to validated data
            validated_data['provider'] = provider
        
        #update with the validated data 
        for field, value in validated_data.items():
            setattr(instance, field, value)  #i.e. instance.field = value

        #update coverage instance and return
        instance.save()
        return instance


#Patient insurance options serializer
@patient_insurance_options_schema
class PatientCoverageOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    insuranceProviderChoices = serializers.SerializerMethodField()
    eligibilityStatusChoices = serializers.SerializerMethodField()

    #Get branches choices (with name and id)
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

    #Get patients choices (with id and name)
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_patientChoices(self, obj):
        branchId = self.context.get('branchId')
        doctorId = self.context.get('doctorId') 
        
        if (not branchId and Branch.objects.exists()) and not doctorId:
            return []
        
        filters = {}
        if branchId:
            filters['branch_id'] = branchId
        if doctorId:
            filters['doctor_id'] = doctorId
        
        return [
            {'patientId': patient_id, 'name': name}
             for patient_id, name in Patient.objects.filter(**filters)\
              .values_list('id', 'name').order_by('name')
        ]

    #Get insurance providers choices (with id and name)
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
                {'providerId': provider_id, 'name': name} 
                    for provider_id,name in InsuranceProvider.objects.filter(**filters)\
                    .values_list('id', 'name').order_by('name')
                ]

    #Get eligibility status choices
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_eligibilityStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
             for choice in PatientCoverage.EligibilityStatusChoices
        ]
