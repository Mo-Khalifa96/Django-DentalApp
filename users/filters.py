
from clinic.models import Branch
from utils.validators import validate_uuid
from users.models import User, DoctorSchedule, DoctorScheduleException
from django_filters.rest_framework import (FilterSet, ChoiceFilter, ModelChoiceFilter, 
                                           DateFilter, BooleanFilter)


#FILTERSETS 
#Users filter 
class UsersFilter(FilterSet):
    role = ChoiceFilter(choices=User.UserRoles.choices)
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())

    class Meta:
        model = User
        fields = []


#Doctor schedules filter 
class DoctorSchedulesFilter(FilterSet):
    doctorId = ModelChoiceFilter(field_name='doctor', queryset=User.objects.all())
    branchId = ModelChoiceFilter(field_name='branch', queryset=Branch.objects.all())
    exceptionDate = DateFilter(field_name='exceptions__date', lookup_expr='exact')
    exceptionType = ChoiceFilter(field_name='exceptions__type', 
        choices=DoctorScheduleException.ExceptionTypeChoices.choices
     )

    class Meta:
        model = DoctorSchedule
        fields = []

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     if not self.request or not hasattr(self.request, 'user'):
    #         return None
        
    #     branchId = validate_uuid(self.request.query_params.get('branchId'))
    #     if branchId:
    #         doctors_queryset = User.objects.filter(branches__id=branchId)
    #     else:
    #         doctors_queryset = User.objects.all()
        
    #     #assign queryset based on above filtering
    #     self.filters['doctorId'].queryset = doctors_queryset
