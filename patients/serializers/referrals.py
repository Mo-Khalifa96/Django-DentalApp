from users.models import User
from clinic.models import Branch
from django.db import transaction
from rest_framework import serializers
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from services.translation.serializers import TranslatedChoiceField
from patients.models import Patient, InboundReferral, OutboundReferral
from patients.docs import referrals_options_schema



#SERIALIZERS FOR INBOUND REFERRALS
#Inbound referrals serializer -- base serializer
class InboundReferralSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=False, allow_null=False)
    patientCount = serializers.IntegerField(read_only=True)
    speciality = TranslatedChoiceField(choices=InboundReferral.SpecialityChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    referredByUserId = serializers.PrimaryKeyRelatedField(source='referredByUser', 
                queryset=User.objects.filter(role__in=['admin', 'dentist', 'assistant']), 
                required=False, allow_null=True)

    class Meta:
        model = InboundReferral
        fields = ['id', 'name', 'clinic', 'speciality', 'phone', 'email', 'notes', 
                  'patientCount', 'referredByUserId', 'branchId', 'createdAt']


#Create inbound referral serializer
class CreateInboundReferralSerializer(ValidateBranchMixin, InboundReferralSerializer):
    class Meta(InboundReferralSerializer.Meta):
        fields = ['id', 'name', 'clinic', 'speciality', 'phone', 'email', 'notes', 
                  'referredByUserId', 'branchId', 'createdAt']
        read_only_fields = ['id', 'createdAt']

    def validate(self, data):
        name = data.get('name')
        referred_by_user = data.get('referredByUser')

        #Validate name against referrer
        if not referred_by_user and not name:
            raise serializers.ValidationError({'name': _("Referrer's name is required when no system doctor is assigned.")})
        
        #Validate referrer is not already there
        if referred_by_user and InboundReferral.objects.filter(
            referredByUser=referred_by_user, branch=data.get('branch')
        ).exists():
            raise serializers.ValidationError({'referredByUserId': _('This doctor is already registered as a referral source for this branch.')})
        return data


#Update inbound referral serializer 
class UpdateInboundReferralSerializer(InboundReferralSerializer): 
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)

    class Meta(InboundReferralSerializer.Meta):
        fields = ['id', 'name', 'clinic', 'speciality', 'phone', 'email', 'notes', 
                  'referredByUserId', 'branchId', 'createdAt']
        read_only_fields = ['id', 'branchId', 'createdAt']
    

    def validate(self, data):
        name = data.get('name', self.instance.name)
        referred_by_user = data.get('referredByUser', self.instance.referredByUser)

        #Validate name against referrer
        if not referred_by_user and not name:
            raise serializers.ValidationError({'name': _("Referrer's name is required when no system doctor is assigned.")})

        #Validate referrer is not already there
        if referred_by_user and referred_by_user != self.instance.referredByUser:
            if InboundReferral.objects.filter(
                referredByUser=referred_by_user, branch=self.instance.branch
            ).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(
                    {'referredByUserId': _('This doctor is already registered as a referral source for this branch.')}
                )

        return data


##########################


#SERIALIZERS FOR OUTBOUND REFERRALS 
#Outbound referrals serializer -- base serializer
class OutboundReferralSerializer(UserPermissionsMixin, serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=False, allow_null=False)
    status = TranslatedChoiceField(choices=OutboundReferral.ReferralStatusChoices.choices, required=False, allow_blank=True, allow_null=True)
    patientName = serializers.CharField(source='patient.name', read_only=True)
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    referredToEntityId = serializers.PrimaryKeyRelatedField(source='referredToEntity', queryset=InboundReferral.objects.all(), required=False, allow_null=True)
    referredToUserId = serializers.PrimaryKeyRelatedField(source='referredToUser', 
                queryset=User.objects.filter(role__in=['admin', 'dentist', 'assistant']),
                required=False, allow_null=True)

    class Meta:
        model = OutboundReferral
        fields = ['id', 'name', 'patientId', 'patientName', 'status', 'outcome', 'notes', 
                  'referredToUserId', 'referredToEntityId', 'branchId', 'createdAt', 'updatedAt']   


#Create outbound referral serializer
class CreateOutboundReferralSerializer(ValidateBranchMixin, OutboundReferralSerializer):
    class Meta(OutboundReferralSerializer.Meta):
        fields = ['id', 'name', 'patientId', 'patientName', 'status', 'outcome', 'notes', 
                  'referredToUserId', 'referredToEntityId', 'branchId', 'createdAt']
        read_only_fields = ['id', 'patientId', 'patientName', 'createdAt']

    def validate(self, data):
        name = data.get('name')
        referred_to_user = data.get('referredToUser')
        referred_to_entity = data.get('referredToEntity')

        #Referred-to-user and referred-to-entity are mutual exclusivie
        if referred_to_user and referred_to_entity:
            raise serializers.ValidationError(_('A referral record cannot target both a system doctor and an outside referral source. Choose one or the other.'))

        #validate name when no referral source is provided
        if not referred_to_user and not referred_to_entity and not name:
            raise serializers.ValidationError({'name': _('Name is required when no system doctor or a known referral source is assigned.')})

        #assign patient ID from url if not provided
        data['patient_id'] = self.context.get('patient_id')

        return data
    
    @transaction.atomic 
    def create(self, validated_data):
        #call parent create() to create referral instance
        referral = super().create(validated_data)

        #update patient's referral
        referred_to_user = referral.referredToUser
        if referred_to_user:
            referral.patient.referredBy = InboundReferral.objects.filter(
             referredByUser_id=referred_to_user.id, branch=referral.branch).first()
            referral.patient.referredByName = referred_to_user.name
            referral.patient.save(update_fields=['referredBy', 'referredByName', 'updatedAt'])

        return referral 


#Update outbound referral serializer 
class UpdateOutboundReferralSerializer(OutboundReferralSerializer):  
    patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)

    class Meta(OutboundReferralSerializer.Meta):
        fields = ['id', 'name', 'patientId', 'patientName', 'status', 'outcome', 'notes',
                  'referredToUserId', 'referredToEntityId', 'branchId', 'updatedAt']
        read_only_fields = ['id', 'patientId', 'patientName', 'branchId', 'updatedAt']


    def validate(self, data):
        name = data.get('name', self.instance.name)
        referred_to_user = data.get('referredToUser', self.instance.referredToUser)
        referred_to_entity = data.get('referredToEntity', self.instance.referredToEntity)

        #Referred-to-user and referred-to-entity are mutual exclusive
        if referred_to_user and referred_to_entity:
            raise serializers.ValidationError(_('A referral record cannot target both a system doctor and an outside referral source. Choose one or the other.'))

        #At least `name` must be provided when source is null
        if not referred_to_user and not referred_to_entity and not name:
            raise serializers.ValidationError({'name': _('Name is required when no system doctor or a known referral source is assigned.')})
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        #call parent update() to update referral instance
        referral = super().update(instance, validated_data)

        #update patient referral if referrer changed
        referred_to_user = validated_data.get('referredToUser') or None
        if referred_to_user and referred_to_user != instance.referredToUser:
            referral.patient.referredBy = InboundReferral.objects.filter(
             referredByUser_id=referred_to_user.id, branch=referral.branch).first()
            referral.patient.referredByName = referred_to_user.name
            referral.patient.save(update_fields=['referredBy', 'referredByName', 'updatedAt'])

        return referral


#Update outbound referral serializer for status updates only
class PatchOutboundStatusSerializer(serializers.ModelSerializer):  
    status = TranslatedChoiceField(choices=OutboundReferral.ReferralStatusChoices.choices, required=True)

    class Meta:
        model = OutboundReferral
        fields = ['status']
    
    @transaction.atomic
    def update(self, instance, validated_data):
        status = validated_data['status']
        instance.status = status 
        instance.save(update_fields=['status', 'updatedAt'])
        return instance


##########################


#Referrals options serializer
@referrals_options_schema 
class ReferralsOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    patientChoices = serializers.SerializerMethodField()
    doctorChoices = serializers.SerializerMethodField()
    referredToEntityChoices = serializers.SerializerMethodField()
    specialityChoices = serializers.SerializerMethodField()
    outboundReferralStatusChoices = serializers.SerializerMethodField()

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
    

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_doctorChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId, 'role__in': ['dentist', 'admin']} if branchId else {'role__in': ['dentist', 'admin']}

        return [
                {'doctorId': doctor_id, 'doctorName': name}
                 for doctor_id,name in User.objects.only('id','name','role', 'branch')\
                    .filter(**filters).values_list('id', 'name').order_by('name')
            ]
    

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_referredToEntityChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId} if branchId else {}
        return [
            {'referredToEntityId': entity_id, 'name': name}
             for entity_id,name in InboundReferral.objects.only('id', 'name', 'branch')\
                .filter(**filters).values_list('id', 'name').order_by('name')
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
    ))
    def get_specialityChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in InboundReferral.SpecialityChoices
        ]
    
    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_outboundReferralStatusChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in OutboundReferral.ReferralStatusChoices
        ]


