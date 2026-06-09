from django.db.models import F,Q
from clinic.models import Branch
from patients.models import Patient
from utils.filters import BaseFilterSet
from finances.models import Bill, Transaction, Invoice
from django_filters.rest_framework import (FilterSet, CharFilter, ChoiceFilter, ModelChoiceFilter, 
                                           BooleanFilter, DateFilter)


#FILTERSETS 
#Bills filter 
class BillsFilter(FilterSet):  #BaseFilterSet
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    patientId = ModelChoiceFilter(field_name='patient', queryset=Patient.objects.all())
    status = ChoiceFilter(choices=[('unpaid', 'unpaid'), ('partial', 'partial'), ('paid', 'paid')])
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


