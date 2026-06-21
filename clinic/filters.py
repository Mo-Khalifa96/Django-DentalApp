from users.models import User
from utils.filters import BaseFilterSet
from patients.models import Patient, Appointment
from django.db.models import F, Q, Func, Value, CharField
from clinic.models import Branch, Procedure, Inventory, Lab, LabOrder, WaitingRoom, SterilizationLog
from django_filters.rest_framework import (FilterSet, CharFilter, ChoiceFilter, ModelChoiceFilter, 
                                           BooleanFilter, DateFilter)


#FILTERSETS 
#Dashboard/appointments filter
class DashboardAppointmentsFilter(FilterSet):   # BaseFilterSet
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    doctorId = ModelChoiceFilter(field_name='doctor', queryset=User.objects.filter(role__in=['admin', 'dentist', 'assistant']))
    status = ChoiceFilter(choices=Appointment.AppointmentStatusChoices.choices)

    class Meta:
        model = Appointment
        fields = []
    
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     #get branch filter 
    #     branch_filter = self.get_branch_filter()
    #     if branch_filter is None:  
    #         #if user has no branches and branches exist
    #         self.filters['doctorId'].queryset = User.objects.none()
    #         return
        
    #     available_branches_list = list(branch_filter.values())
    #     if available_branches_list:
    #         if isinstance(available_branches_list[0], list):
    #             doctors_queryset = User.objects.filter(branches__id__in=available_branches_list[0])
    #         else:
    #             doctors_queryset = User.objects.filter(branches__id=available_branches_list[0])
    #     else:
    #         doctors_queryset = User.objects.all()
    #     self.filters['doctorId'].queryset = doctors_queryset


#Procedures filter 
class ProceduresFilter(FilterSet):
    category = ChoiceFilter(choices=Procedure.ProcedureCategory.choices)
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())

    class Meta:
        model = Procedure
        fields = []


#Inventory filter 
class InventoryFilter(BaseFilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    lowStock = BooleanFilter(method='filter_low_stock')
    category = ChoiceFilter(field_name='category')

    def filter_low_stock(self, queryset, name, value):
        if value == True:
            return queryset.filter(currentStock__lt=F('minStock'))
        elif value == False:
            return queryset.filter(currentStock__gte=F('minStock'))
        return queryset

    class Meta:
        model = Inventory
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #get branch filter 
        branch_filter = self.get_branch_filter()
        if branch_filter is None:
            self.filters['category'].field.choices = []
            return

        #filter by branch (if provided)
        available_categories = Inventory.objects.filter(**branch_filter)\
                .values_list('category', flat=True).distinct().order_by('category')

        #populated filter field with the obtained choices
        self.filters['category'].field.choices = [(cat, cat) for cat in available_categories if cat]

    #NOTE - switch to charfield if choices aren't served properly
    #Example:
    # category = CharFilter(method='filter_category')

    # def filter_category(self, queryset, name, value):
    #     branch_filter = self.get_branch_filter()
    #     if branch_filter is None:
    #         return queryset.none()
    #     valid_categories = Inventory.objects.filter(**branch_filter)\
    #         .values_list('category', flat=True).distinct()
    #     if value not in valid_categories:
    #         return queryset.none()
    #     return queryset.filter(category=value)


#Labs filter 
class LabsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())

    class Meta:
        model = Lab 
        fields = []


#Lab orders filter
class LabOrdersFilter(FilterSet):
    labId = ModelChoiceFilter(field_name='lab', queryset=Lab.objects.all())
    patientId = ModelChoiceFilter(field_name='patient', queryset=Patient.objects.all())
    procedureId = ModelChoiceFilter(field_name='procedure', queryset=Procedure.objects.all())
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    status = ChoiceFilter(choices=LabOrder.OrderStatusChoices.choices)
    sentDate = DateFilter(field_name='sentDate', lookup_expr='exact')
    dueDate = DateFilter(field_name='dueDate', lookup_expr='exact')
    receivedDate = DateFilter(field_name='receivedDate', lookup_expr='exact')
    deliveredDate = DateFilter(field_name='deliveredDate', lookup_expr='exact')

    class Meta:
        model = LabOrder
        fields = []
    
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     #get branch filter 
    #     branch_filter = self.get_branch_filter()
    #     if branch_filter is None:
    #         #if user has no branches and branches exist
    #         self.filters['labId'].queryset = Lab.objects.none()
    #         self.filters['patientId'].queryset = Patient.objects.none()
    #         self.filters['procedureId'].queryset = Procedure.objects.none()
    #         return
        
    #     #filter by branch (if provided)
    #     self.filters['labId'] = Lab.objects.filter(**branch_filter)
    #     self.filters['patientId'] = Patient.objects.filter(**branch_filter)
    #     self.filters['procedureId'] = Procedure.objects.filter(**branch_filter)


#Sterilization logs filter 
class SterilizationLogsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    date = DateFilter(field_name='date', lookup_expr='exact')
    sealedAt = DateFilter(field_name='sealedAt', lookup_expr='exact')
    search = CharFilter(method='filter_search')
    result = ChoiceFilter(choices=SterilizationLog.SterilizationResultChoices.choices)

    #Custom method for case-insensitive searching by 'operator', 'cycleType', & 'instrumentSets'
    def filter_search(self, queryset, name, value):
        return queryset.annotate(
            instrumentSets_text=Func(
                'instrumentSets', Value(' '),
                function='array_to_string', output_field=CharField(),
            )
        ).filter(
            Q(operator__icontains=value) | 
            Q(cycleType__icontains=value) | 
            Q(instrumentSets_text__icontains=value)
        )
    
    class Meta:
        model = SterilizationLog
        fields = []


#Waiting room filter
class WaitingRoomFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    date = DateFilter(field_name='arrivedAt', lookup_expr='date')

    class Meta:
        model = WaitingRoom
        fields = []
