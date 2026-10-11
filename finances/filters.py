from decimal import Decimal
from clinic.models import Branch
from utils.filters import BaseFilterSet
from patients.models import Patient, PatientCoverage
from finances.models import Bill, Transaction, Invoice, InstallmentPlan, InsuranceProvider
from django_filters.rest_framework import (FilterSet, ChoiceFilter, ModelChoiceFilter, 
                                           BooleanFilter, DateFilter)


#FILTERSETS 
#Bills filter 
class BillsFilter(FilterSet):  #BaseFilterSet
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    patientId = ModelChoiceFilter(field_name='patient', queryset=Patient.objects.all())
    status = ChoiceFilter(choices=Bill.BillStatusChoices.choices)
    date = DateFilter(field_name='createdAt', lookup_expr='date')
    hasInstallmentPlan = BooleanFilter(method='filter_byInstPlan')
    isDeleted = BooleanFilter(method='filter_deleted')

    class Meta:
        model = Bill 
        fields = []

    def filter_deleted(self, queryset, name, value):
        if value == False:
            return queryset.filter(isDeleted=False)
        elif value == True:
            return queryset.filter(isDeleted=True)
        return queryset
    
    def filter_byInstPlan(self, queryset, name, value):
        if value == False:
            return queryset.filter(hasInstallmentPlan=False)
        elif value == True:
            return queryset.filter(hasInstallmentPlan=True)
        return queryset

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     #get branch filter 
    #     branch_filter = self.get_branch_filter()
    #     if branch_filter is None:
    #         #if user has no branches and branches exist
    #         self.filters['patientId'].queryset = Patient.objects.none()
    #         return
        
    #     #filter by branch (if provided)
    #     self.filters['patientId'] = Patient.objects.filter(**branch_filter)


#Transactions filter
class TransactionsFilter(FilterSet):
    billId = ModelChoiceFilter(field_name='bill', queryset=Bill.objects.all())
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    patientId = ModelChoiceFilter(field_name='patient', queryset=Patient.objects.all())
    date = DateFilter(field_name='date', lookup_expr='exact')
    type = ChoiceFilter(choices=Transaction.TransactionTypeChoices.choices)
    status = ChoiceFilter(choices=Transaction.TransactionStatusChoices.choices)
    isDeleted = BooleanFilter(method='filter_deleted')

    def filter_deleted(self, queryset, name, value):
        if value == False:
            return queryset.filter(isDeleted=False)
        elif value == True:
            return queryset.filter(isDeleted=True)
        return queryset

    class Meta:
        model = Transaction
        fields = []


#Invoices filter
class InvoicesFilter(FilterSet):
    billId = ModelChoiceFilter(field_name='bill', queryset=Bill.objects.all())
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    patientId = ModelChoiceFilter(field_name='patient', queryset=Patient.objects.all())
    status = ChoiceFilter(choices=Invoice.InvoiceStatusChoices.choices)
    issuedAt = DateFilter(field_name='issuedAt', lookup_expr='date')
    submittedAt = DateFilter(field_name='submittedAt', lookup_expr='date')
    isDeleted = BooleanFilter(method='filter_deleted')

    def filter_deleted(self, queryset, name, value):
        if value == False:
            return queryset.filter(isDeleted=False)
        elif value == True:
            return queryset.filter(isDeleted=True)
        return queryset

    class Meta:
        model = Invoice
        fields = []


#Installments filter
class InstallmentsFilter(FilterSet):
    billId = ModelChoiceFilter(field_name='bill', queryset=Bill.objects.all())
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    status = ChoiceFilter(choices=InstallmentPlan.InstallmentPlanStatusChoices.choices)
    installmentMonths = ChoiceFilter(choices=InstallmentPlan.InstallmentMonthsChoices.choices)
    paidAt = DateFilter(field_name='installments__paidAt', lookup_expr='date')

    class Meta:
        model = InstallmentPlan
        fields = []



#Patient accounts filter 
class PatientAccountsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    insuranceCoverageStatus = ChoiceFilter(field_name='patient_insurance__eligibilityStatus', choices=PatientCoverage.EligibilityStatusChoices.choices)
    hasCreditHeld = BooleanFilter(method='filter_byCreditHeld')
    hasPendingInstallments = BooleanFilter(method='filter_byPendingInstallments')
    hasPendingPayments = BooleanFilter(method='filter_byPendingPayments')


    def filter_byCreditHeld(self, queryset, name, value):
        if value == False:
            return queryset.filter(totalCreditHeld=Decimal('0'))
        elif value == True:
            return queryset.filter(totalCreditHeld__gt=Decimal('0'))
        return queryset
    
    def filter_byPendingInstallments(self, queryset, name, value):
        if value == False:
            return queryset.filter(pendingInstallmentsCount=0)
        elif value == True:
            return queryset.filter(pendingInstallmentsCount__gt=0)
        return queryset
    
    def filter_byPendingPayments(self, queryset, name, value):
        if value == False:
            return queryset.filter(unsettledBillsCount=0)
        elif value == True:
            return queryset.filter(unsettledBillsCount__gt=0)
        return queryset
    
    class Meta:
        model = Patient 
        fields = []



#Insurance providers filter
class InsuranceProvidersFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    tier = ChoiceFilter(choices=InsuranceProvider.InuranceTierChoices.choices)

    class Meta:
        model = InsuranceProvider
        fields = []

#Insurance providers statistics filter
class InsuranceProvidersStatsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    providerId = ModelChoiceFilter(field_name='id', queryset=InsuranceProvider.objects.all())
    tier = ChoiceFilter(choices=InsuranceProvider.InuranceTierChoices.choices)

    class Meta:
        model = InsuranceProvider
        fields = []

