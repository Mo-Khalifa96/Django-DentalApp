from users.models import User
from clinic.models import Branch
from utils.filters import BaseFilterSet
from finances.models import InsuranceProvider
from django.db.models import Q, Func, Value, CharField
from patients.models import Patient, Visit, Appointment, TreatmentPlan, PatientCoverage, PatientRecall
from django_filters.rest_framework import (FilterSet, CharFilter, ChoiceFilter, ModelChoiceFilter, DateFilter, BooleanFilter)


#FILTERSETS 
#Patients filter
class PatientsFilter(BaseFilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    status = ChoiceFilter(choices=[('active', 'active'), ('inactive', 'inactive')])
    insuranceProvider = ChoiceFilter(field_name='patient_insurance__provider__name',
     choices=[
        (name,name) for name in InsuranceProvider.objects.values_list('name', flat=True).order_by('name')
     ])
    # # insuranceProviderId = ModelChoiceFilter(field_name='patient_insurance__provider__name',
    # #                                         queryset=InsuranceProvider.objects.all())

    class Meta:
        model = Patient
        fields = []

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     #get branch filter 
    #     branch_filter = self.get_branch_filter()
    #     if branch_filter is None:
    #         self.filters['insuranceProvider'].field.choices = []
    #         return
        
    #     #filter by branch (if provided)
    #     insurance_providers = InsuranceProvider.objects.filter(**branch_filter)\
    #             .values_list('name', flat=True).order_by('name')
        
    #     #populate field choices with available insurance providers
    #     self.filters['insuranceProvider'].field.choices = [(provider, provider) for provider in insurance_providers]


#Visits filter 
class VisitsFilter(FilterSet):
    startDate = DateFilter(field_name='date', lookup_expr='gte')
    endDate = DateFilter(field_name='date', lookup_expr='lte')
    search = CharFilter(method='filter_search')

    #Custom method for case-insensitive searching by visit 'type' and 'procedures'
    def filter_search(self, queryset, name, value):
        return queryset.annotate(
            procedures_text=Func(
                'procedures', Value(' '),
                function='array_to_string', output_field=CharField(),
            )
        ).filter(
            Q(type__icontains=value) | 
            Q(procedures_text__icontains=value)
        )

    class Meta:
        model = Visit
        fields = []


#Appointments filter 
class AppointmentsFilter(BaseFilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    doctorId = ModelChoiceFilter(field_name='doctor', queryset=User.objects.filter(role__in=['admin', 'dentist', 'assistant']))
    status = ChoiceFilter(choices=Appointment.AppointmentStatusChoices.choices)
    date = DateFilter(field_name='date', lookup_expr='exact')
    startDate = DateFilter(field_name='date', lookup_expr='gte')
    endDate = DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = Appointment
        fields = []

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     #get branch filter 
    #     branch_filter = self.get_branch_filter()
    #     if branch_filter is None:
    #         self.filters['doctorName'].field.choices = []
    #         return

    #     #filter by branch (if provided)
    #     #Get doctor names list
    #     doctor_names = User.objects.filter(**branch_filter, role__in=['dentist', 'admin'])\
    #         .values_list('name', flat=True).distinct().order_by('name')
     
    #     #populated filter fields with the obtained choices
    #     self.filters['doctorName'].field.choices = [(cat, cat) for cat in doctor_names if cat]        


#Treatment plans filter 
class TreatmentPlansFilter(FilterSet):
    status = ChoiceFilter(choices=TreatmentPlan.TreatmentStatusChoices.choices)

    class Meta:
        model = TreatmentPlan
        fields = []


#Patient coverage filter 
class PatientCoverageFilter(FilterSet):
    eligibilityStatus = ChoiceFilter(choices=PatientCoverage.EligibilityStatusChoices.choices)
    deductibleMet = BooleanFilter()
    effectiveFrom = DateFilter(lookup_expr='gte')
    effectiveTo = DateFilter(lookup_expr='lte')

    class Meta:
        model = PatientCoverage
        fields = []


#Patient recalls filter 
class PatientRecallsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    dueDate = DateFilter(field_name='dueDate', lookup_expr='exact')
    status = ChoiceFilter(choices=PatientRecall.RecallStatusChoices.choices)
    type = ChoiceFilter(choices=PatientRecall.RecallTypeChoices.choices)

    class Meta:
        model = PatientRecall
        fields = []
