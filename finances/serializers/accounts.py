from rest_framework import serializers
from patients.models import PatientCoverage
from utils.mixins import UserPermissionsMixin
from django.utils.translation import gettext_lazy as _
from services.translation.serializers import TranslatedChoiceField


#PATIENT ACCOUNTS SERIALIZERS
#List patient accounts serializer
class ListPatientAccountsSerializer(serializers.Serializer):
    #patient and their bills
    patientId = serializers.UUIDField(source='id', allow_null=True)
    patientName = serializers.CharField(source='name', allow_null=True)
    totalBilled = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    
    #outstanding money
    totalOutstanding = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    #bill-related
    unsettledBillsCount = serializers.IntegerField(allow_null=True)
    totalBilledOutstanding = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    #installments-related
    pendingInstallmentsCount = serializers.IntegerField(allow_null=True)
    totalInstallmentsOutstanding = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)

    #money paid (transactions)
    totalCollected = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    collectedFromPatient = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    collectedFromInsurer = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    totalCreditHeld = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)  #NOTE: deposit and other withheld money
    # currency = serializers.CharField(allow_null=True)

    #insurer details
    insuranceCoverageStatus = TranslatedChoiceField(choices=PatientCoverage.EligibilityStatusChoices.choices, read_only=True)
    coverageEffectiveTo = serializers.DateField(allow_null=True)
    insuranceAnnualMax = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    insuranceUsedYTD = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    yearlyBenefitRemaining = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)

    #bill updatedAt date
    lastBillUpdatedAt = serializers.DateTimeField(allow_null=True)


#Patient account serializer
class PatientAccountSerializer(UserPermissionsMixin, serializers.Serializer):
    #patient and their bills
    patientId = serializers.UUIDField(allow_null=True)
    patientName = serializers.CharField(allow_null=True)
    totalBilled = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    
    #outstanding money
    totalOutstanding = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    #bill-related
    unsettledBillsCount = serializers.IntegerField(allow_null=True)
    totalBilledOutstanding = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    #installments-related
    pendingInstallmentsCount = serializers.IntegerField(allow_null=True)
    totalInstallmentsOutstanding = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)

    #money paid (transactions)
    totalCollected = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    collectedFromPatient = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    collectedFromInsurer = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    totalCreditHeld = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    # currency = serializers.CharField(allow_null=True)

    #insurer details
    insuranceCoverageStatus = TranslatedChoiceField(choices=PatientCoverage.EligibilityStatusChoices.choices, read_only=True)
    coverageEffectiveTo = serializers.DateField(allow_null=True)
    insuranceAnnualMax = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    insuranceUsedYTD = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
    yearlyBenefitRemaining = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)
