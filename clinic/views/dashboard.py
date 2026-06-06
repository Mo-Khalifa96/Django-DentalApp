from utils.base_views import *
from clinic.models import Branch
from datetime import date, timedelta
from django.db.models import Q, Count, Sum
from rest_framework import status, generics
from rest_framework.response import Response
from finances.models import Transaction, Bill
from patients.models import Patient, Appointment
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from users.permissions import SystemUserPermissions
from clinic.filters import DashboardAppointmentsFilter
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from utils.pagination import DashboardAppointmentsPagination
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from utils.mixins import BranchToFilterMixin, BranchToSerializerMixin, FilterByBranchMixin
from clinic.serializers.dashboard import (DashboardStatisticsSerializer, DashboardAppointmentTodaySerializer, 
                                        DashboardQueryParamSerializer, DashboardOptionsSerializer)


#DASHBOARD API VIEWS
#Dashboard Statistics API view
@extend_schema(
    tags=['Dashboard'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('dateRange', OpenApiTypes.STR, OpenApiParameter.QUERY, enum=['today', 'week', 'month'], required=False),
    ]
)
class DashboardStatisticsAPIView(GenericAPIView):
    serializer_class = DashboardStatisticsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        #Get date today and work days window
        today = date.today()  #date today 
        days_since_saturday = (today.weekday() + 2) % 7
        staring_saturday = today - timedelta(days=days_since_saturday)
        ending_friday = staring_saturday + timedelta(days=6)

        #serializer query parameters (if any)
        queryparam_serializer = DashboardQueryParamSerializer(data=request.query_params)
        queryparam_serializer.is_valid(raise_exception=True)
        dateRange = queryparam_serializer.validated_data.get('dateRange')
        branchId = queryparam_serializer.validated_data.get('branchId')

        #Filter by user's branch if non-admin
        if not branchId and getattr(request.user, 'role', None) != 'admin':
            branch = getattr(request.user, 'branch', None)
            branchId = branch.id if branch else None

        #COMPUTE REQUIRED DATA 

        #Fetch model data by branch (if provided)
        branch_filter = Q(branch_id=branchId) if branchId else Q()

        #get all necessary querysets
        appointments = Appointment.objects.only('id', 'patient', 'date', 'branch').filter(branch_filter).exclude(status='cancelled')
        patients = Patient.objects.only('id', 'createdAt', 'branch').filter(branch_filter)
        # visits = Visit.objects.only('id', 'cost', 'paid').filter(patient__branch=branch_filter)
        transactions = Transaction.objectsonly('id', 'amount', 'branch').filter(branch_filter)
        bills = Bill.objects.only('id', 'totalAmount', 'branch').filter(branch_filter)


        #Define filters based on date range query
        if not dateRange:
            #Default filters
            new_patients_filter = Q(createdAt__month=today.month, createdAt__year=today.year)
            appointments_count_filter = Q(date__exact=today)
            completed_appointments_filter = Q(status='completed', date__month=today.month, date__year=today.year)
            revenue_filter = Q(date__month=today.month, date__year=today.year)

        elif dateRange == 'today':
            new_patients_filter = Q(createdAt__date=today)
            appointments_count_filter = Q(date__exact=today)
            completed_appointments_filter = Q(status='completed', date__exact=today)
            revenue_filter = Q(date__exact=today)
        
        elif dateRange == 'week':
            new_patients_filter = Q(createdAt__date__range=(staring_saturday, ending_friday))
            appointments_count_filter = Q(date__range=(staring_saturday, ending_friday))
            completed_appointments_filter = Q(status='completed', date__range=(staring_saturday, ending_friday))
            revenue_filter = Q(date__range=(staring_saturday, ending_friday))
           
        elif dateRange == 'month':
            new_patients_filter = Q(createdAt__month=today.month, createdAt__year=today.year)
            appointments_count_filter = Q(date__month=today.month, date__year=today.year)
            completed_appointments_filter = Q(status='completed', date__month=today.month, date__year=today.year)
            revenue_filter = Q(date__month=today.month, date__year=today.year)


        #Aggregate data based on relevant filters
        #get total patients and total new patients
        patients_aggregates = patients.aggregate(
            patientsTotal=Count('id'),  #no filtering
            patientsNew=Count('id', filter=new_patients_filter)
        )

        #get total appointments and total completed
        appointment_aggregates = appointments.aggregate(
            appointmentsCount=Count('id', filter=appointments_count_filter),
            appointmentsCompleted=Count('id', filter=completed_appointments_filter)
        )

        #calculate revenue from transactions 
        payments_aggregates = transactions.aggregate(
            revenue=Sum('amount', filter=revenue_filter),
            total_revenue=Sum('amount'),
            # currency=Max('currency'),
        )

        #calculate total billed for outstanding amount from bills
        total_billed = bills.aggregate(total_billed=Sum('totalAmount'))['total_billed'] or 0

        #calculate outstanding from total revenue
        total_revenue = payments_aggregates['total_revenue'] or 0
        outstanding = round(float(total_billed - total_revenue), 2)

        # #get revenue and total outstanding (irrespective of month)
        # payments_aggregates = visits.aggregate(
        #     revenue=Sum('paid', filter=revenue_filter),
        #     total_revenue=Sum('paid'),
        #     total_cost=Sum('cost'),
        #     # currency=Max('currency'),
        #     )
        
        # #calculate outstanding (total cost not paid)
        # total_revenue = payments_aggregates['total_revenue'] or 0
        # total_cost = payments_aggregates['total_cost'] or 0
        # outstanding = round(float(total_cost) - float(total_revenue), 2)


        #build data
        data = {
            'patientsTotal': patients_aggregates['patientsTotal'],
            'patientsNew': patients_aggregates['patientsNew'],
            'appointmentsCount': appointment_aggregates['appointmentsCount'],
            'appointmentsCompleted': appointment_aggregates['appointmentsCompleted'],
            'revenue': payments_aggregates['revenue'] or 0,
            'outstanding': outstanding,
            # 'currency': payments_aggregates['currency']
        }

        #Serializer data to return response 
        serializer = self.get_serializer(data)

        #return response
        return Response(serializer.data, status=status.HTTP_200_OK)


#Dashboard Appointments Today API View
@extend_schema(tags=['Dashboard'])
class DashboardAppointmentTodayAPIView(FilterByBranchMixin, generics.ListAPIView, BranchToFilterMixin):
    serializer_class = DashboardAppointmentTodaySerializer
    permission_classes = [SystemUserPermissions]
    required_permission = 'view.calender'
    ordering = ['branch__name', 'startTime', 'endTime']  #default order of fields
    ordering_fields = ['startTime', 'endTime', 'status']  #order by date and status
    search_fields = ['patient__name', 'doctor__name', 'status', 'room']  #search by patient name, status, and room
    filterset_class = DashboardAppointmentsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    pagination_class = DashboardAppointmentsPagination

    def get_queryset(self):
        user = self.request.user 
        today = date.today()
        appointments = Appointment.objects\
                        .select_related('patient', 'doctor', 'branch')\
                        .filter(date__exact=today)

        #return full queryset to admin --  TODO: admins gets all appointments irrespective of branch?
        if getattr(user, 'role', None) == 'admin':
            return appointments
        elif getattr(user, 'role', None) == 'dentist':
            #fetch doctor's appointments only
            return appointments.filter(doctor_id=user.id)
        elif self.required_permission in getattr(user, 'userPermissions', []):
            #filter by user's branch
            return self.filter_by_branch(appointments)
        else:
            return appointments.none()


#View for retrieving branch choices for filtering
@extend_schema(
    tags=['Dashboard'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
    ]
)
class DashboardOptionsAPIView(generics.GenericAPIView, BranchToSerializerMixin): 
    queryset = Branch.objects.all()
    serializer_class = DashboardOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
