from django.db import transaction
from rest_framework import serializers
from patients.models import Visit, XRay
from clinic.models import Branch, Procedure
from patients.docs import visit_options_schema
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField


#SERIALIZERS FOR PATIENT VISITS
#Serializer for listing and creating patient visits
class PatientVisitSerializer(serializers.ModelSerializer):
    #patientId = serializers.PrimaryKeyRelatedField(source='patient', read_only=True)
    patientName = serializers.CharField(source='patient.name', read_only=True)
    doctorId = serializers.PrimaryKeyRelatedField(source='doctor', read_only=True)
    doctorName = serializers.CharField(source='doctor.name', read_only=True)
    type = TranslatedChoiceField(choices=Visit.VisitTypeChoices.choices)
    xrayUploads = serializers.ListField(child=serializers.ImageField(required=False, allow_empty_file=True),
                                        required=False, write_only=True, allow_empty=True, allow_null=True)
    xrayUrls = serializers.SerializerMethodField()  #output only

    class Meta:
        model = Visit
        fields = ['id', 'doctorId', 'doctorName', 'patientName', 'date', 'type', 'procedures', 'currency', 
                  'cost', 'paid', 'notes', 'xray', 'xrayUploads', 'xrayUrls', 'createdAt']
        read_only_fields = ['id', 'patientName', 'doctorId', 'doctorName', 'xrayUrls', 'createdAt']
        extra_kwargs = {
            'currency': {'required': False}, 'cost': {'required': False}, 'paid': {'required': False}, 
            'xray': {'default': False}, 'notes': {'required': False}
        }

    @extend_schema_field(serializers.ListField(child=serializers.URLField()))
    def get_xrayUrls(self, obj):
        request = self.context.get('request')
        xrays = obj.patient.patient_xrays.all()
        if request:
            return [request.build_absolute_uri(xray.image.url) for xray in xrays]
        return [xray.image.url for xray in xrays]

    @transaction.atomic 
    def create(self, validated_data):
        #fetch request and patient from context
        request = self.context.get('request')
        patient = self.context['patient']

        #fetch xray uploads before creating visit
        xray_images = validated_data.pop('xrayUploads', [])

        #create visit
        visit = Visit.objects.create(**validated_data,
                                     patient=patient,
                                     doctor=request.user)
        
        #update doctor if None
        if not patient.doctor:
            patient.doctor = request.user
            patient.save(update_fields=['doctor', 'updatedAt'])

        #Handle image uploads
        if xray_images:
            visit.xray = True
            visit.save(update_fields=['xray'])

            xrays_to_upload = [
                XRay(patient=patient, image=image)
                 for image in xray_images
            ]
            
            #upload images to XRay model
            XRay.objects.bulk_create(xrays_to_upload)

        return visit


#Serializer for providing procedure options
@visit_options_schema
class VisitOptionsSerializer(serializers.Serializer):
    branchChoices = serializers.SerializerMethodField()
    visitTypeChoices = serializers.SerializerMethodField()
    optionalProcedureChoices = serializers.SerializerMethodField()
    optionalProcedureTypeChoices = serializers.SerializerMethodField()

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
    def get_visitTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Visit.VisitTypeChoices
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField(allow_blank=True, allow_null=True))
        ))
    def get_optionalProcedureChoices(self, obj):
        branchId = self.context.get('branchId')
        if not branchId and Branch.objects.exists():
            return []
        
        filters = {'branch_id': branchId} if branchId else {}
        return [
            {
                'name': procedure_name,
                'category': procedure_category,
                'duration': duration,
                'price': f'{currency}{price}' if currency else str(price),
            }
            for procedure_name, procedure_category, duration, currency, price 
                in Procedure.objects.filter(**filters).values_list(
                    'name', 'category', 'duration', 'currency', 'price'
                    )
        ]

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_optionalProcedureTypeChoices(self, obj):
        return [
            {'value': choice.value, 'label': str(choice.label)}
            for choice in Procedure.ProcedureCategory
        ]

