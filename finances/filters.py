from django.db.models import F,Q
from clinic.models import Branch
from patients.models import Patient
from utils.filters import BaseFilterSet
from finances.models import Bill, Transaction, Invoice, InstallmentPlan, InsuranceProvider
from django_filters.rest_framework import (FilterSet, CharFilter, ChoiceFilter, ModelChoiceFilter, 
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
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    status = ChoiceFilter(choices=InstallmentPlan.InstallmentPlanStatusChoices.choices)
    installmentMonths = ChoiceFilter(choices=InstallmentPlan.InstallmentMonthsChoices.choices)
    paidAt = DateFilter(field_name='installments__paidAt', lookup_expr='date')

    class Meta:
        model = InstallmentPlan
        fields = []


#Insurance providers filter
class InsuranceProvidersFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    tier = ChoiceFilter(choices=InsuranceProvider.InuranceTierChoices.choices)

    class Meta:
        model = InsuranceProvider
        fields = []