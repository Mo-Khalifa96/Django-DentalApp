from django.db import transaction
from clinic.models import Branch
from django.utils import timezone
from patients.models import Patient
from rest_framework import serializers
from patients.models import PatientCoverage
from finances.models import InsuranceProvider
from utils.mixins import UserPermissionsMixin
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField
from finances.serializers.insurance_providers import CreateNewProviderSerializer
from patients.docs import patient_coverage_stats_schema, patient_insurance_options_schema


#Helpers
#Reference object to patient coverage fields
COVERAGE_FIELDS = ('provider', 'providerName', 'memberId', 'annualMax', 'usedYTD', 'coveragePercent', 
                   'deductibleMet', 'currency', 'effectiveFrom', 'effectiveTo', 'eligibilityStatus',
                   'eligibilityChecked')

def determine_branch(user, coverage):
    '''Helper function to determine branch.'''
    if user.branches.count() == 1:
        return user.branches.first()
    elif getattr(coverage.patient, 'branch_id', None):
        return coverage.patient.branch
    elif getattr(user, 'branch_id', None):
        return user.branch
    elif Branch.objects.exists() and user.branches.exists():
        return user.branches.first()
    else:
        return None

def validate_provider_duplicate(name, branch):
    '''Helper function to validate provider duplication.'''
    #validate provider name/branch duplication
    if InsuranceProvider.objects.filter(name__iexact=name, branch=branch).exists():
        raise serializers.ValidationError({
            'newProviderDetails':  _('A provider with this name already exists. Select it from the list instead.')
        })


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
                  'annualMax', 'coveragePercent', 'deductibleMet', 'usedYTD', 'effectiveFrom', 
                  'effectiveTo', 'eligibilityStatus', 'eligibilityChecked', 'updatedAt']


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
                  'effectiveFrom', 'effectiveTo', 'eligibilityStatus']
        read_only_fields = ['id', 'patientName', 'patientId', 'providerName']
        extra_kwargs = {
            'memberId': {'required': True, 'allow_null': False, 'allow_blank': False},
            **{field: {'required': True} for field in ('effectiveFrom', 'effectiveTo', 'eligibilityStatus')},
            **{field: {'required': False} for field in (
               'providerId', 'is_newProvider', 'newProviderDetails', 'deductibleMet',
               'annualMax', 'usedYTD', 'currency'
               )
            }
        }

    #validate insurer-related data
    def validate(self, data):
        #fetch necessary data for validation
        coverage = self.context.get('coverage')
        existing_provider = data.get('provider')
        is_new_provider = data.get('is_newProvider', False)
        new_provider_details = data.get('newProviderDetails')        
        
        if is_new_provider:
            if not new_provider_details:
                raise serializers.ValidationError({'newProviderDetails': _("Insurance provider's details are required if creating a new provider.")})
            if existing_provider:
                raise serializers.ValidationError({'providerId': _('Cannot assign an existing insurance provider if choosing to create a new one.')})
        else:
            if not existing_provider:
                #update flag if missed or misassigned
                if new_provider_details:
                    data['is_newProvider'] = is_new_provider = True
                else:
                    raise serializers.ValidationError({'providerId': _('An insurance provider is required to create a new insurance plan.')})
        

        if is_new_provider:
            #identify and assign current branch from user
            user = self.context.get('request').user
            data['branch'] = determine_branch(user, coverage)
            #validate provider name/branch duplication
            validate_provider_duplicate(name=new_provider_details['name'], 
                                        branch=data['branch'])
                    
        #anticipate insurance provider change
        if new_provider_details or existing_provider:
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
                                                        branch=branch)

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
                  'newProviderDetails', 'memberId', 'annualMax', 'usedYTD', 'coveragePercent', 'deductibleMet', 'currency',
                  'effectiveFrom', 'effectiveTo', 'eligibilityChecked', 'eligibilityStatus', 'updatedAt']
        read_only_fields = ['id', 'patientName', 'patientId', 'providerName', 'coveragePercent', 'updatedAt']
        extra_kwargs = {
            'memberId': {'allow_null': False, 'allow_blank': False},
            **{field: {'required': False} for field in (
               'providerId', 'is_newProvider', 'newProviderDetails', 'deductibleMet', 
               'annualMax', 'usedYTD', 'currency', 'eligibilityChecked'
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
            self.fields['effectiveFrom'].required = True
            self.fields['effectiveTo'].required = True
            self.fields['eligibilityStatus'].required = True
        else:
            self.fields['memberId'].required = False
            self.fields['effectiveFrom'].required = False
            self.fields['effectiveTo'].required = False
            self.fields['eligibilityStatus'].required = False
            

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if request.method == 'GET':
            if instance and (instance.updatedAt.date() == instance.patient.createdAt.date()):
                rep['updatedAt'] = None
        return rep

    #validate insurer-related data
    def validate(self, data):
        if all([field not in data.keys() for field in ('provider', 'is_newProvider', 'newProviderDetails')]):
            return data 

        coverage = self.instance
        existing_provider = data.get('provider') #or self.instance.provider
        is_new_provider = data.get('is_newProvider', False)
        new_provider_details = data.get('newProviderDetails')

        if is_new_provider:
            if not new_provider_details:
                raise serializers.ValidationError({'newProviderDetails': _("Insurance provider's details are required if creating a new provider.")})
            if existing_provider:
                raise serializers.ValidationError({'providerId': _('Cannot assign an existing insurance provider if choosing to create a new one.')})
        else:
            if not existing_provider:
                if new_provider_details:
                    data['is_newProvider'] = is_new_provider = True
                elif 'provider' in data:  #i.e., intentional clearing
                    #if intentionally removing insurance coverage -- set field values to None
                    for field in COVERAGE_FIELDS:
                        data[field] = None
        
        if is_new_provider:
            #identify and assign current branch from user
            user = self.context.get('request').user
            data['branch'] = determine_branch(user, coverage)
            #validate provider name/branch duplication
            validate_provider_duplicate(name=new_provider_details['name'],
                                        branch=data['branch'])
        
        #anticipate insurance provider change
        if new_provider_details or (existing_provider and existing_provider != self.instance.provider):
            #check if they supply the necessary information with the new provider
            required_fields = ('memberId', 'effectiveFrom', 'effectiveTo', 'eligibilityStatus')
            missing_fields = {
                field: _('This field is required when assigning a new insurance provider.')
                 for field in required_fields if field not in data
            }

            if missing_fields:
                raise serializers.ValidationError(missing_fields)
            
            #null out current coverage details
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
                                                  branch=branch)

            #add new provider object to validated data
            validated_data['provider'] = provider

        else:
            if ('effectiveTo' in validated_data and 'eligibilityStatus' not in validated_data
             and instance.eligibilityStatus in ('active', 'expiring', 'expired')):
                instance.effectiveTo = validated_data.pop('effectiveTo')
                validated_data['eligibilityStatus'] = instance.determine_coverage_status(instance.eligibilityStatus)
                validated_data['eligibilityChecked'] = timezone.localdate(timezone.now())

        #update with the validated data 
        for field, value in validated_data.items():
            setattr(instance, field, value)  #i.e. instance.field = value

        #update coverage instance and return
        instance.save()
        return instance


#Patient coverage stats serializer
@patient_coverage_stats_schema
class PatientCoverageStatisticsSerializer(UserPermissionsMixin, serializers.Serializer):
    insuredPatients = serializers.IntegerField(allow_null=True)
    byEligibility = serializers.DictField(child=serializers.IntegerField(allow_null=True), allow_null=True)
    annualMaxTotal = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)
    usedYTDTotal = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)
    remainingTotal = serializers.DecimalField(max_digits=20, decimal_places=2, allow_null=True)
    utilisationPercent = serializers.IntegerField(allow_null=True)


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

