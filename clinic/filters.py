from users.models import User
from django.db.models import F
from patients.models import Appointment
from clinic.models import Branch, Procedure, Inventory, Lab, LabOrder, WaitingRoom, SterilizationLog
from django_filters.rest_framework import (FilterSet, CharFilter, ChoiceFilter, ModelChoiceFilter, 
                                           BooleanFilter, DateFilter)


#FILTERSETS 
#Dashboard/appointments filter
class DashboardAppointmentsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    doctorId = ModelChoiceFilter(field_name='doctor', queryset=User.objects.all())
    status = ChoiceFilter(choices=Appointment.AppointmentStatusChoices.choices)

    class Meta:
        model = Appointment
        fields = []

    # def __init__(self, *args, **kwargs):
    #     branch_id = kwargs.pop('branch_id', None)
    #     super().__init__(*args, **kwargs)
    #     if branch_id:
    #         doctors_queryset = User.objects.filter(branch_id=branch_id)
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
class InventoryFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    lowStock = BooleanFilter(method='filter_low_stock')
    category = ChoiceFilter()

    def filter_low_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(currentStock__lt=F('minStock'))
        elif value is False:
            return queryset.filter(currentStock__gte=F('minStock'))
        return queryset

    class Meta:
        model = Inventory
        fields = []

    def __init__(self, *args, **kwargs):
        branch_id = kwargs.pop('branch_id', None)
        super().__init__(*args, **kwargs)
        #Initialize category choices
        #filter by branch (if provided)
        inventory_filter = {'branch_id': branch_id} if branch_id else None
        available_categories = Inventory.objects.filter(**inventory_filter)\
                .values_list('category', flat=True).distinct().order_by('category')

        #populated filter field with the obtained choices
        self.filters['category'].field.choices = [(cat, cat) for cat in available_categories if cat]


#Labs filter 
class LabsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())

    class Meta:
        model = Lab 
        fields = []


#Lab orders filter
class LabOrdersFilter(FilterSet):
    labId = ModelChoiceFilter(field_name='lab', queryset=Branch.objects.all())
    patientId = ModelChoiceFilter(field_name='patient', queryset=Branch.objects.all())
    procedureId = ModelChoiceFilter(field_name='procedure', queryset=Branch.objects.all())
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    status = ChoiceFilter(choices=LabOrder.OrderStatusChoices.choices)
    sentDate = DateFilter(field_name='sentDate', lookup_expr='exact')
    dueDate = DateFilter(field_name='dueDate', lookup_expr='exact')
    receivedDate = DateFilter(field_name='receivedDate', lookup_expr='exact')
    deliveredDate = DateFilter(field_name='deliveredDate', lookup_expr='exact')

    class Meta:
        model = LabOrder
        fields = []


#Sterilization logs filter 
class SterilizationLogsFilter(FilterSet):
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    date = DateFilter(field_name='date', lookup_expr='exact')
    sealedAt = DateFilter(field_name='sealedAt', lookup_expr='exact')
    search = CharFilter(field_name='instrumentSets', lookup_expr='icontains')
    result = ChoiceFilter(choices=SterilizationLog.SterilizationResultChoices.choices)

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
