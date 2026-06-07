from users.models import User
from clinic.models import Branch
from patients.models import Patient, Visit, Appointment, TreatmentPlan, PatientRecall
from django_filters.rest_framework import (CharFilter, FilterSet, ChoiceFilter, ModelChoiceFilter, DateFilter)


#FILTERSETS 
#Patients filter
class PatientsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    status = ChoiceFilter(choices=[('active', 'active'), ('inactive', 'inactive')])
    insurance = ChoiceFilter()

    class Meta:
        model = Patient
        fields = []

    def __init__(self, *args, **kwargs):
        branch_id = kwargs.pop('branch_id', None)
        super().__init__(*args, **kwargs)
        #Initialize insurance choices for insurance filter
        #filter by branch (if provided)
        insurance_filter = {'branch_id': branch_id} if branch_id else {}
        insurance_providers = Patient.objects.filter(**insurance_filter)\
                .values_list('insurance', flat=True)\
                .distinct().order_by('insurance')
        
        #populate field choices with available insurance providers
        self.filters['insurance'].field.choices = [(provider, provider) for provider in insurance_providers]


#Visits filter 
class VisitsFilter(FilterSet):
    startDate = DateFilter(field_name='date', lookup_expr='gte')
    endDate = DateFilter(field_name='date', lookup_expr='lte')
    search = CharFilter(field_name='procedures', lookup_expr='icontains')

    class Meta:
        model = Visit
        fields = []


#Appointments filter 
class AppointmentsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    status = ChoiceFilter(choices=Appointment.AppointmentStatusChoices.choices)
    date = DateFilter(field_name='date', lookup_expr='exact')
    startDate = DateFilter(field_name='date', lookup_expr='gte')
    endDate = DateFilter(field_name='date', lookup_expr='lte')
    patientName = ChoiceFilter(field_name='patient__name')
    doctorName = ChoiceFilter(field_name='doctor__name')

    class Meta:
        model = Appointment
        fields = []

    def __init__(self, *args, **kwargs):
        branch_id = kwargs.pop('branch_id', None)
        super().__init__(*args, **kwargs)

        #filter by branch (if provided)
        patients_filter = {'branch_id': branch_id} if branch_id else {}
        users_filters = {'role': 'dentist', 'branch_id': branch_id} if branch_id else {'role': 'dentist'}
        
        #fetch available choices
        patient_names = Patient.objects.filter(**patients_filter)\
                .values_list('name', flat=True).distinct().order_by('name')
        #Get doctor names list
        doctor_names = User.objects.filter(**users_filters)\
            .values_list('name', flat=True).distinct().order_by('name')
     
        #populated filter fields with the obtained choices
        self.filters['patientName'].field.choices = [(cat, cat) for cat in patient_names if cat]
        self.filters['doctorName'].field.choices = [(cat, cat) for cat in doctor_names if cat]        


#Treatment plans filter 
class TreatmentPlansFilter(FilterSet):
    status = ChoiceFilter(choices=TreatmentPlan.TreatmentStatusChoices.choices)

    class Meta:
        model = TreatmentPlan
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
