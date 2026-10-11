from decimal import Decimal
from clinic.models import Branch
from django.db import transaction
from rest_framework import serializers
from django.db.models.functions import Coalesce
from utils.swagger_utils import extend_schema_field
from django.utils.translation import gettext_lazy as _
from django.core.files.storage import default_storage
from utils.mixins import UserPermissionsMixin, ValidateBranchMixin
from services.translation.serializers import TranslatedChoiceField
from finances.models import Bill, InstallmentPlan, InsuranceProvider
from patients.models import Patient, PatientDocument, XRay, InboundReferral
from django.db.models import F, Sum, ExpressionWrapper, Exists, DecimalField, OuterRef
from patients.docs import (create_patient_schema, full_update_patient_schema, 
                           partial_update_patient_schema, patients_options_schema)


#SERIALIZERS FOR PATIENTS
#Serializer for patient documents -- Nested serializer 
class PatientDocumentsSerializer(serializers.ModelSerializer):
    type = TranslatedChoiceField(choices=PatientDocument.DocumentTypeChoices.choices, 
                                 required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = PatientDocument
        fields = ['document', 'fileName', 'type', 'contentType', 'sizeBytes', 'notes', 'uploadedBy', 'uploadedAt']
        read_only_fields = ['fileName', 'contentType', 'sizeBytes', 'uploadedBy', 'uploadedAt']

#Serializer for creating new patient
@create_patient_schema
class CreatePatientSerializer(ValidateBranchMixin, serializers.ModelSerializer):
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', queryset=Branch.objects.all(), required=True, allow_null=True)
    insurance = serializers.CharField(source='patient_insurance.providerName', default=None, read_only=True)
    insuranceProviderId = serializers.PrimaryKeyRelatedField(queryset=InsuranceProvider.objects.all(),
                                        required=False, default=None, allow_null=True, write_only=True)
    referredById = serializers.PrimaryKeyRelatedField(source='referredBy', queryset=InboundReferral.objects.all(),
                                                      required=False, allow_null=True)
    documents = PatientDocumentsSerializer(many=True, source='patient_documents', required=False,
                                           allow_null=True, allow_empty=True)
    # documentUrls = serializers.SerializerMethodField()  #output only

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId',
                  'bloodType', 'allergies', 'insurance', 'insuranceProviderId', 'notes', 'status', 
                  'referredById', 'referredByName', 'branchId', 'documents', 'createdAt', 'updatedAt']
        read_only_fields = ['id', 'insurance', 'status', 'referredByName', 'createdAt', 'updatedAt']


    # @extend_schema_field(serializers.ListField(child=serializers.URLField()))
    # def documentUrls(self, obj):
    #     request = self.context.get('request')
    #     documents = obj.patient_documents.all()
    #     if request:
    #         return [request.build_absolute_uri(doc.document.url) for doc in documents]
    #     return [doc.document.url for doc in documents]


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

    def to_internal_value(self, data):
        #parse incoming data correctly
        if hasattr(data, 'dict'):
            data = data.dict()
        
        return super().to_internal_value(data) 

    @transaction.atomic
    def create(self, validated_data):
        #fetch insurance provider before creating patient
        provider = validated_data.pop('insuranceProviderId', None)

        #fetch document uploads before creating patient
        documents = validated_data.pop('patient_documents', [])

        #create patient instance
        patient = Patient(**validated_data) #Patient.objects.create(**validated_data)
        patient.save(provider=provider)

        #Handle document uploads 
        if documents:
            user = self.context.get('request').user

            docs_to_upload = [
                PatientDocument(
                    patient=patient,
                    document=doc['document'],
                    type=doc.get('type'),
                    fileName=doc['document'].name,
                    contentType=getattr(doc['document'], 'content_type', None),
                    sizeBytes=doc['document'].size,
                    notes=doc.get('notes'),
                    uploadedBy=user.name,
                )
                for doc in documents   #doc is a dictionary
            ]

            #upload documents to PatientDocument model
            PatientDocument.objects.bulk_create(docs_to_upload)

        return patient


#Serializer for patient listing 
class ListPatientSerializer(serializers.ModelSerializer): 
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    insurance = serializers.CharField(source='patient_insurance.providerName', read_only=True)
    insuranceId = serializers.CharField(source='patient_insurance.memberId', read_only=True)
    outstandingBalance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'phone', 'email', 'address', 'nationalId', 'bloodType', 
                  'allergies', 'insurance', 'insuranceId', 'outstandingBalance', 'lastVisit', 'nextAppointment', 
                  'notes', 'status', 'branchId', 'createdAt', 'updatedAt']


#Serializer for retrieving patient details 
class RetrievePatientSerializer(UserPermissionsMixin, serializers.ModelSerializer): 
    gender = TranslatedChoiceField(choices=Patient.GenderChoices.choices)
    branchId = serializers.PrimaryKeyRelatedField(source='branch', read_only=True)
    insurance = serializers.CharField(source='patient_insurance.providerName', read_only=True)
    insuranceId = serializers.CharField(source='patient_insurance.memberId', read_only=True)
    referredById = serializers.PrimaryKeyRelatedField(source='referredBy', read_only=True)
    documents = PatientDocumentsSerializer(many=True, source='patient_documents', read_only=True)
    outstandingBalance = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    
    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId',
                  'bloodType', 'allergies', 'insurance', 'insuranceId', 'outstandingBalance', 'lastVisit', 
                  'nextAppointment', 'notes', 'status', 'referredById', 'referredByName', 'branchId', 
                  'documents', 'createdAt', 'updatedAt']
    
    @extend_schema_field(serializers.CharField)
    def get_phone(self, obj):
        return '0' + obj.phone[len(obj.countryCode):]

    @extend_schema_field(serializers.DecimalField(max_digits=10, decimal_places=2))
    def get_outstandingBalance(self, obj):
        #get outstanding from all bills
        bills_outstanding = obj.patient_bills.filter(isDeleted=False, isDepositBill=False)\
            .annotate(
                total_outstanding=ExpressionWrapper(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')), 
                    output_field=DecimalField())
        ).values('total_outstanding')

        #account for installment plans with no active bill generated
        installments_outstanding = InstallmentPlan.objects.filter(treatment__patient=obj)\
            .annotate(
                has_active_bill=Exists(
                    Bill.objects.earnings().filter(treatment_id=OuterRef('treatment_id'))
                )
            ).filter(has_active_bill=False).annotate(
                total_outstanding=ExpressionWrapper(
                    F('totalAmount') - Coalesce(F('totalPaid'), Decimal('0')), 
                    output_field=DecimalField())
        ).values('total_outstanding')

        #sum them together with a single query
        outstanding_balance = bills_outstanding.union(installments_outstanding, all=True)\
            .aggregate(total=Sum('total_outstanding', default=Decimal('0')))['total']
        
        #Serialize value upon returning it
        outstanding_balance = outstanding_balance if outstanding_balance > 0 else Decimal('0')
        return serializers.DecimalField(max_digits=10, decimal_places=2).to_representation(outstanding_balance)


#Serializer for PUT-only requests to update patient details with documents
@full_update_patient_schema
class FullUpdatePatientSerializer(serializers.ModelSerializer):
    status = TranslatedChoiceField(choices=Patient.StatusChoices.choices, required=False)
    insurance = serializers.CharField(source='patient_insurance.providerName', default=None, read_only=True)
    insuranceProviderId = serializers.PrimaryKeyRelatedField(queryset=InsuranceProvider.objects.all(), 
                                                        required=False, allow_null=True, write_only=True)
    referredById = serializers.PrimaryKeyRelatedField(source='referredBy', queryset=InboundReferral.objects.all(), 
                                                      required=False, allow_null=True)
    documents = PatientDocumentsSerializer(many=True, source='patient_documents', required=False,
                                           allow_null=True, allow_empty=True)

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId', 
                  'bloodType', 'allergies', 'insurance', 'insuranceProviderId', 'notes', 'status', 
                  'referredById', 'referredByName', 'documents', 'updatedAt']
        read_only_fields = ['id', 'insurance', 'referredByName', 'updatedAt']
        # extra_kwargs = {field: {'required': False} for field in 
        #     ('name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId', 
        #      'bloodType', 'allergies', 'insuranceProviderId', 'notes', 'status')
        #     }
    
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

    def to_internal_value(self, data):
        #parse incoming data correctly
        if hasattr(data, 'dict'):
            data = data.dict()
        return super().to_internal_value(data) 

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
        
        #Handle document uploads        
        #check if documents are passed at all
        if 'patient_documents' in validated_data:       #delete old documents and write-over
            existing_docs = instance.patient_documents.all()
            for doc in existing_docs:
                doc.document.delete(save=False)  #deletes file from DB
            existing_docs.delete()  #deletes rows
        
        #fetch document uploads before creating patient
        documents = validated_data.pop('patient_documents', [])
        
        if documents:
            user = self.context.get('request').user

            #handle uploads
            docs_to_upload = [
                PatientDocument(
                    patient=instance,
                    document=doc['document'],
                    type=doc.get('type'),
                    fileName=doc['document'].name,
                    contentType=getattr(doc['document'], 'content_type', None),
                    sizeBytes=doc['document'].size,
                    notes=doc.get('notes'),
                    uploadedBy=user.name,
                )
                for doc in documents
            ]
            
            #bulk-create documents
            PatientDocument.objects.bulk_create(docs_to_upload)

        #call parent update() method
        return super().update(instance, validated_data)


#Serializer for PATCH only requests to update patient details without documents
@partial_update_patient_schema
class PartialUpdatePatientSerializer(serializers.ModelSerializer):
    status = TranslatedChoiceField(choices=Patient.StatusChoices.choices, required=False)
    insurance = serializers.CharField(source='patient_insurance.providerName', default=None, read_only=True)
    insuranceProviderId = serializers.PrimaryKeyRelatedField(queryset=InsuranceProvider.objects.all(), 
                                                        required=False, allow_null=True, write_only=True)
    referredById = serializers.PrimaryKeyRelatedField(source='referredBy', queryset=InboundReferral.objects.all(),
                                                      required=False, allow_null=True)
    documents = PatientDocumentsSerializer(many=True, source='patient_documents', read_only=True)   #read only

    class Meta:
        model = Patient
        fields = ['id', 'name', 'age', 'gender', 'countryCode', 'phone', 'email', 'address', 'nationalId', 
                  'bloodType', 'allergies', 'insurance', 'insuranceProviderId', 'notes', 'status', 
                  'referredById', 'referredByName', 'documents', 'updatedAt']
        read_only_fields = ['id', 'insurance', 'referredByName', 'documents', 'updatedAt']

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
    documentTypeChoices = serializers.SerializerMethodField()

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

    @extend_schema_field(
        serializers.ListField(
            child=serializers.DictField(child=serializers.CharField())
        ))
    def get_documentTypeChoices(self, obj):
        return [
            {'value': choice[0], 'label': choice[1]}
            for choice in PatientDocument.DocumentTypeChoices
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


#Serializer for individual document uploads
class UploadDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientDocument
        fields = ['document']
        extra_kwargs = {'document': {'required': True}}
    
    @transaction.atomic
    def create(self, validated_data):
        #get patient id from context
        patient_id = self.context.get('patient_id')
        uploaded_document = validated_data['document'] 

        #create document upload instance
        document = PatientDocument.objects.create(
            patient_id=patient_id, 
            document=uploaded_document,
            fileName=uploaded_document.name,
            contentType=getattr(uploaded_document, 'content_type', None),
            sizeBytes=uploaded_document.size
        )
        return document
    

#Serializer for deleting files (documents or images)
class DeleteFileSerializer(serializers.Serializer):
    url = serializers.URLField()

    def validate_url(self, url):
        media_url = default_storage.url("")

        if not url.startswith(media_url):
            raise serializers.ValidationError(_('Invalid file URL.'))
        
        #extract file name
        file_name = url[len(media_url):]

        try:
            url_file = PatientDocument.objects.only('document').get(document=file_name)
        except PatientDocument.DoesNotExist:
            try:
                url_file = XRay.objects.only('image').get(image=file_name)
            except XRay.DoesNotExist:
                raise serializers.ValidationError(_('File not found or does not exist.'))
            except XRay.MultipleObjectsReturned:
                raise serializers.ValidationError(_('Multiple files match the provided url.'))
        except PatientDocument.MultipleObjectsReturned:
            raise serializers.ValidationError(_('Multiple files match the provided url.'))

        self.url_file = url_file
        return url_file

    @transaction.atomic
    def delete_file(self):
        #get file
        url_file = self.url_file

        #delete the physical file
        if hasattr(url_file, 'document'):
            url_file.document.delete(save=False)
        elif hasattr(url_file, 'image'):
            url_file.image.delete(save=False)

        #delete file's database record
        url_file.delete()
