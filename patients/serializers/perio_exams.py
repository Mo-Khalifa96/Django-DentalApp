import copy
from django.utils import timezone
from django.db import transaction
from rest_framework import serializers
from patients.models import PerioExam
from patients.validators import FDI_PERMANENT
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
# from patients.docs import retrieve_perio_exam_schema, perio_exams_options_schema


#Valid tooth sites
VALID_TOOTH_SITES = {'DB', 'B', 'MB', 'DP', 'P', 'MP'}


#Helper mixin to add attachment loss
class AttachmentLossMixin:
    def to_representation(self, instance):
        data = super().to_representation(instance)
        #Derive attachment loss per site (computed on read)
        teeth = copy.deepcopy(data.get('teeth') or {})
        for tooth_dict in teeth.values():
            for site_data in tooth_dict.get('sites', {}).values():
                probing_depth = site_data.get('probingDepth')
                recession = site_data.get('recession')
                
                #calculate attachment loss
                if probing_depth is not None and recession is not None:
                    site_data['attachmentLoss'] = (probing_depth + recession)
                else:
                    site_data['attachmentLoss'] = None

        data['teeth'] = teeth
        return data

#PERIOCHART SERIALIZERS
#List patient periodontal exams summary serializer
class ListPerioExamsSummarySerializer(serializers.ModelSerializer):
    examinedById = serializers.PrimaryKeyRelatedField(source='examinedBy', read_only=True)

    class Meta:
        model = PerioExam
        fields = ['id', 'meanProbingDepth', 'bleedingPercent', 'sitesProbed', 'notes',
                  'examinedById', 'examinedByName', 'examinedAt']


#Retrieve periodontal exam serializer
# @retrieve_perio_exam_schema
class RetrievePerioExamSerializer(AttachmentLossMixin, serializers.ModelSerializer):
    examinedById = serializers.PrimaryKeyRelatedField(source='examinedBy', read_only=True)
    
    class Meta:
        model = PerioExam
        fields = ['id', 'teeth', 'meanProbingDepth', 'bleedingPercent', 'sitesProbed',
                  'notes', 'examinedById', 'examinedByName', 'examinedAt']


#Tooth site serializer  -- double nested serializer
class ToothSiteSerializer(serializers.Serializer):
    probingDepth = serializers.IntegerField(allow_null=True, required=False, 
      validators=[
        MinValueValidator(0, message=_('Probing depth must be between 0mm and 13mm.')),
        MaxValueValidator(13, message=_('Probing depth must be between 0mm and 13mm.')),
    ])
    recession = serializers.IntegerField(allow_null=True, required=False)
    bleeding = serializers.BooleanField(allow_null=True, default=False)
    plaque = serializers.BooleanField(allow_null=True, default=False)
    suppuration = serializers.BooleanField(allow_null=True, default=False)
    calculus = serializers.BooleanField(allow_null=True, default=False)


#Tooth serializer -- nested serializer
class PerioToothDetailSerializer(serializers.Serializer):
    mobility = serializers.IntegerField(allow_null=True, required=False, 
      validators=[
        MinValueValidator(0, message=_('Mobility value must be between 0 and 3.')),
        MaxValueValidator(3, message=_('Mobility value must be between 0 and 3.')),
    ])
    furcation = serializers.IntegerField(allow_null=True, required=False, 
      validators=[
        MinValueValidator(0, message=_('Furcation value must be between 0 and 3.')),
        MaxValueValidator(3, message=_('Furcation value must be between 0 and 3.')),
    ])
    sites = serializers.DictField(child=ToothSiteSerializer(many=False))


#Create periodontal exam serializer
class CreatePerioExamSerializer(AttachmentLossMixin, serializers.ModelSerializer):
    teeth = serializers.DictField(child=PerioToothDetailSerializer(many=False))
    examinedById = serializers.PrimaryKeyRelatedField(source='examinedBy', read_only=True)

    class Meta:
        model = PerioExam
        fields = ['id', 'teeth', 'meanProbingDepth', 'bleedingPercent', 'sitesProbed', 'notes', 
                  'examinedById', 'examinedByName', 'examinedAt']
        read_only_fields = ['id', 'meanProbingDepth', 'bleedingPercent', 'sitesProbed',
                            'examinedById', 'examinedByName', 'examinedAt']


    def validate_teeth(self, teeth):
        #prepare errors dict
        errors = {}

        #iterate over each tooth and its data
        for tooth_number, tooth_dict in teeth.items():
            #validate tooth number (FDI notation)
            if tooth_number not in FDI_PERMANENT:
                errors[tooth_number] = _('Invalid tooth number. Does not comply with FDI notation.')
                continue
            
            #validate tooth site
            invalid_sites = set(tooth_dict.get('sites', {})) - VALID_TOOTH_SITES
            if invalid_sites:
                errors[tooth_number] = _('Invalid tooth site(s): %(sites)s') % {'sites': ', '.join(sorted(invalid_sites))}

        #raise errors (if any)
        if errors:
            raise serializers.ValidationError(errors)
        
        #return teeth
        return teeth

    @transaction.atomic    
    def create(self, validated_data):
        user = self.context['request'].user
        teeth = validated_data['teeth']

        #get exam summary stats 
        exam_summary = PerioExam.compute_perio_summary(teeth)

        sites_count = exam_summary[0]
        probingDepth_mean = exam_summary[1]
        bleeding_perc = exam_summary[2]

        #create exam object
        perio_exam = PerioExam.objects.create(
            patient_id=self.context['patient_id'],  #passed from serializer context
            teeth=teeth,
            sitesProbed=sites_count,
            meanProbingDepth=probingDepth_mean,
            bleedingPercent=bleeding_perc,
            notes=validated_data.get('notes'),
            examinedBy_id=user.id,
            examinedByName=user.name,
            examinedAt=timezone.localdate(timezone.now()),
        )

        return perio_exam 


#Update periodontal exam serializer
class UpdatePerioExamSerializer(CreatePerioExamSerializer):   #PUT only
    class Meta(CreatePerioExamSerializer.Meta):
        fields = ['id', 'teeth', 'meanProbingDepth', 'bleedingPercent', 'sitesProbed', 'notes']
        read_only_fields = ['id', 'meanProbingDepth', 'bleedingPercent', 'sitesProbed']

    @transaction.atomic
    def update(self, instance, validated_data):
        #get updated teeth
        teeth = validated_data.get('teeth')
        
        #update exam's teeth
        instance.teeth = teeth

        #compute exam summary stats 
        exam_summary = PerioExam.compute_perio_summary(teeth)

        #update exam summary stats
        instance.sitesProbed = exam_summary[0]
        instance.meanProbingDepth = exam_summary[1]
        instance.bleedingPercent = exam_summary[2]
        
        #update notes (if any)
        instance.notes = validated_data.get('notes')

        #save exam changes
        instance.save()
        return instance


#Periodontal exams options serializer
# @perio_exams_options_schema
class PerioExamOptionsSerializer(serializers.Serializer):
    toothNumberChoices = serializers.SerializerMethodField()
    toothSiteChoices = serializers.SerializerMethodField()

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
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
    ))
    def get_toothSiteChoices(self, obj):
        return [
            {'value': choice, 'label': choice} for choice in VALID_TOOTH_SITES
        ]
