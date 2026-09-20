from utils.base_views import *
from decimal import Decimal
from django.utils import timezone
from datetime import date, timedelta
from rest_framework import status, generics
from rest_framework.response import Response
from finances.models import Transaction, Bill
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from django.db.models.functions import Coalesce
from users.permissions import SystemUserPermissions
from clinic.filters import DashboardAppointmentsFilter
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from clinic.models import Branch, WaitingRoom, Inventory
from django_filters.rest_framework import DjangoFilterBackend
from utils.pagination import DashboardAppointmentsPagination
from services.translation.mixins import FieldsTranslationMixin
from utils.mixins import BranchToSerializerMixin, FilterByBranchMixin
from patients.models import Patient, Appointment, Visit, PatientRecall
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import Q, F, Avg, Sum, Count, ExpressionWrapper, Exists, OuterRef, DurationField, IntegerField
from clinic.serializers.dashboard import (DashboardStatisticsSerializer, DashboardAppointmentTodaySerializer, 
                                        DashboardQueryParamSerializer, DashboardOptionsSerializer)


#Helpers
def get_quarter(today: date):
    month, year = today.month, today.year

    if month in [1,2,3]:
        # start_date = date(year=year, month=1, day=1)
        # end_date = date(year=year, month=3, day=31)
        return (date(year, 1, 1), date(year, 3, 31))
    elif month in [4,5,6]:
        return (date(year, 4, 1), date(year, 6, 30))
    elif month in [7,8,9]:
        return (date(year, 7, 1), date(year, 9, 30))
    elif month in [10,11,12]:
        return (date(year, 10, 1), date(year, 12, 31))


#DASHBOARD API VIEWS
#Dashboard Statistics API view
@extend_schema(
    tags=['Dashboard'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('dateRange', OpenApiTypes.STR, OpenApiParameter.QUERY, 
                         enum=['today', 'week', 'month', 'quarter', 'year'], required=False),
    ]
)
class DashboardStatisticsAPIView(GenericAPIView):
    serializer_class = DashboardStatisticsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        #Get current user 
        user = request.user 

        #Prepare data dict
        data = {
            'patientsTotal': None,
            'patientsNew': None,
            'appointmentsCount': None,
            'appointmentsCompleted': None,
            'appointmentsCancelled': None,
            'appointmentsNoShow': None,
            'revenue': None,
            'waitingRoom': None,
            'recalls': None,
            'inventory': None
        }

        #Prepare conditions
        is_admin = getattr(user, 'role', None) == 'admin'
        has_clinicalAnalytics_permission = 'view.clinicalAnalytics' in getattr(request.user, 'userPermissions', [])
        has_financialAnalytics_permission = 'view.financialAnalytics' in getattr(request.user, 'userPermissions', [])

        if not (
         is_admin or 
         has_clinicalAnalytics_permission or 
         has_financialAnalytics_permission):
            #return null data
            serializer = self.get_serializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)

        #Prepare filtering
        #get date today and work days window
        local_datetime = timezone.localtime(timezone.now())
        today = local_datetime.date()
        yesterday = today - timedelta(days=1)
        days_since_saturday = (today.weekday() + 2) % 7
        starting_saturday = today - timedelta(days=days_since_saturday)
        ending_friday = starting_saturday + timedelta(days=6)

        #serializer query parameters (if any)
        queryparam_serializer = DashboardQueryParamSerializer(data=request.query_params, context=self.get_serializer_context())
        queryparam_serializer.is_valid(raise_exception=True)
        dateRange = queryparam_serializer.validated_data.get('dateRange')
        branchId = queryparam_serializer.validated_data.get('branchId')

        #DEFINE FILTERS
        #Filter by branchId (if provided) or user's branch if non-admin
        if branchId:
            branch_filter = Q(branch_id=branchId)
        elif getattr(user, 'role', None) == 'admin'\
         or not Branch.objects.exists():
            branch_filter = Q()
        elif user.branches.count() == 1:
            branch_filter = Q(branch_id=user.branches.first().id)
        elif getattr(user, 'branch_id', None):
            branch_filter = Q(branch_id=user.branch_id)
        else:
            #fallback
            branch_ids = user.branches.values_list('id', flat=True)
            branch_filter = Q(branch_id__in=branch_ids) if branch_ids else Q()
        

        #Define complex filters
        #define the missed appointments filter -- defaulting to `today` only
        missed_appointments_today = (
            Q(date__exact=today, 
              status__in=['pending', 'confirmed'], 
              in_waiting_room__isnull=True
            )
            &
            (Q(endTime__isnull=False, endTime__lt=local_datetime.time()) 
              |   #OR
             Q(endTime__isnull=True, startTime__lte=(local_datetime - timedelta(hours=1)).time())
            )
        )


        #Define filters based on date range query
        if not dateRange:
            #Default filters
            createdAt_filter = Q(createdAt__month=today.month, createdAt__year=today.year) #used for new patients and bills
            date_filter = Q(date__exact=today)  #used with 'appointments' and 'revenue'
            appointmentsNoShow_filter = missed_appointments_today

        elif dateRange == 'today':
            createdAt_filter = Q(createdAt__date=today)
            date_filter = Q(date__exact=today)
            appointmentsNoShow_filter = missed_appointments_today
        
        elif dateRange == 'week':
            createdAt_filter = Q(createdAt__date__range=(starting_saturday, ending_friday))
            date_filter = Q(date__range=(starting_saturday, ending_friday))
            appointmentsNoShow_filter = (
             missed_appointments_today if today == starting_saturday
             else (
                missed_appointments_today |
                Q(date__range=(starting_saturday, yesterday),
                  status__in=['pending', 'confirmed'],
                  in_waiting_room__isnull=True, 
                ) 
                & ~Exists(Visit.objects.filter(patient=OuterRef('patient'), date=OuterRef('date')))
                # & ~Q(patient__patient_visits__date__exact=F('date'))
            ))

        elif dateRange == 'month':
            createdAt_filter = Q(createdAt__month=today.month, createdAt__year=today.year)
            date_filter = Q(date__month=today.month, date__year=today.year)
            appointmentsNoShow_filter = (
             missed_appointments_today if today.day == 1
             else (
                missed_appointments_today |
                Q(date__range=(date(year=today.year, month=today.month, day=1), yesterday),
                  status__in=['pending', 'confirmed'],
                  in_waiting_room__isnull=True, 
                ) 
                & ~Exists(Visit.objects.filter(patient=OuterRef('patient'), date=OuterRef('date')))
            ))


        elif dateRange == 'quarter':
            #determine current quarter
            quarter_range = get_quarter(today)
            createdAt_filter = Q(createdAt__date__range=quarter_range)
            date_filter = Q(date__range=quarter_range)
            appointmentsNoShow_filter = (
             missed_appointments_today if today == quarter_range[0]
             else (
                missed_appointments_today |
                Q(date__range=(quarter_range[0], yesterday),
                  status__in=['pending', 'confirmed'],
                  in_waiting_room__isnull=True, 
                ) 
                & ~Exists(Visit.objects.filter(patient=OuterRef('patient'), date=OuterRef('date')))
            ))

        elif dateRange == 'year':
            createdAt_filter = Q(createdAt__year=today.year)
            date_filter = Q(date__year=today.year)
            appointmentsNoShow_filter = (
             missed_appointments_today if yesterday.year < today.year
             else (
                missed_appointments_today |
                Q(date__range=(date(year=today.year, month=1, day=1), yesterday),
                  status__in=['pending', 'confirmed'],
                  in_waiting_room__isnull=True, 
                ) 
                & ~Exists(Visit.objects.filter(patient=OuterRef('patient'), date=OuterRef('date')))
            ))


        #CLINICAL ANALYTICS
        #if admin or has permission
        if is_admin or has_clinicalAnalytics_permission:
            #Get necessary querysets for clinical analytics
            patients = Patient.objects.only('id', 'createdAt', 'branch').filter(branch_filter)
            
            appointments = Appointment.objects.only(
                'id', 'patient', 'date', 'status', 'startTime', 'endTime', 'branch'
            ).select_related('in_waiting_room').filter(branch_filter)
            
            waiting_room = WaitingRoom.objects.only(
                'id', 'status', 'arrivedAt', 'startedAt', 'branch'
            ).filter(branch_filter & Q(arrivedAt__date=today))

            recalls = PatientRecall.objects\
                .only('id', 'dueDate', 'status', 'branch'
            ).filter(branch_filter & Q(status__in=['pending', 'no_answer']))
            
            inventory = Inventory.objects.only(
                'id', 'currentStock', 'minStock', 'branch'
            ).filter(branch_filter)


            #CLINICAL ANALYTICS
            #Aggregate data based on relevant filters
            #get patients aggregates
            patients_aggregates = patients.aggregate(
                patientsTotal=Count('id'),  #no filtering
                patientsNew=Count('id', filter=createdAt_filter)
            )

            #get appointments aggregates
            appointments_aggregates = appointments.aggregate(
                appointmentsCount=Count('id', filter=date_filter),
                appointmentsCompleted=Count('id', filter=Q(status='completed') & date_filter),
                appointmentsCancelled=Count('id', filter=Q(status='cancelled') & date_filter),
                appointmentsNoShow=Count('id', filter=appointmentsNoShow_filter & date_filter),
            )

            #get waiting room aggregates
            waiting_room_aggregates = waiting_room.aggregate(
                waiting=Count('id', filter=Q(status='waiting')),
                inChair=Count('id', filter=Q(status='in_chair')),
                doneToday=Count('id', filter=Q(status='done')),
                avgWait=Avg(
                    ExpressionWrapper(
                        F('startedAt') - F('arrivedAt'),
                        output_field=DurationField()
                    ),
                    filter=Q(startedAt__isnull=False)
                ),
            )

            #Get average waiting time
            avg_wait = waiting_room_aggregates['avgWait']
            avg_wait_minutes = round(avg_wait.total_seconds()/60) if (avg_wait is not None) else None

            #get recalls aggregates
            recalls_aggregates = recalls.aggregate(
                overdue=Count('id', filter=Q(dueDate__lt=today)),
                dueToday=Count('id', filter=Q(dueDate__exact=today)),
                dueThisWeek=Count('id', filter=Q(dueDate__range=(starting_saturday, ending_friday)))
            )

            #get inventory aggregates
            inventory_aggregates = inventory.annotate(
                    criticalThreshold=ExpressionWrapper(F('minStock')/2, output_field=IntegerField())
                ).aggregate(
                    lowStock=Count('id', filter=Q(currentStock__lt=F('minStock'))),
                    criticalStock=Count('id', filter=Q(currentStock__lte=F('criticalThreshold')))
                )

            #Add computed data to the data dictioary
            data['patientsTotal'] = patients_aggregates['patientsTotal']
            data['patientsNew'] = patients_aggregates['patientsNew']
            data['appointmentsCount'] = appointments_aggregates['appointmentsCount']
            data['appointmentsCompleted'] = appointments_aggregates['appointmentsCompleted']
            data['appointmentsCancelled'] = appointments_aggregates['appointmentsCancelled']
            data['appointmentsNoShow'] = appointments_aggregates['appointmentsNoShow']
            data['waitingRoom'] = {
                'waiting': waiting_room_aggregates['waiting'],
                'inChair': waiting_room_aggregates['inChair'],
                'doneToday': waiting_room_aggregates['doneToday'],
                'avgWaitMinutes': avg_wait_minutes
            }
            data['recalls'] = {
                'overdue': recalls_aggregates['overdue'],
                'dueToday': recalls_aggregates['dueToday'],
                'dueThisWeek': recalls_aggregates['dueThisWeek'],

            }
            data['inventory'] = {
                'lowStock': inventory_aggregates['lowStock'],
                'criticalStock': inventory_aggregates['criticalStock']
            }
            

        #FINANCIAL ANALYTICS
        #if admin or has permission
        if is_admin or has_financialAnalytics_permission:
            #Get necessary querysets for financial analytics
            bills = Bill.objects.only('id', 'totalAmount', 'createdAt', 'branch').filter(branch_filter)
            transactions = Transaction.objects.only('id', 'amount', 'method', 'date', 'branch').filter(branch_filter)

            #get billing aggregates
            bills_aggregates = bills.aggregate(
                total_billed=Coalesce(Sum('totalAmount'), Decimal('0')),  #used for calculating 'totalOutstanding' only
                billed_in_range=Coalesce(Sum('totalAmount', filter=createdAt_filter), Decimal('0'))   #for 'billedInPeriod'
            )

            transactions_aggregates = transactions.aggregate(
                total_revenue=Coalesce(Sum('amount'), Decimal('0')), #used for calculating 'totalOutstanding' only
                revenue_in_range=Coalesce(Sum('amount', filter=date_filter), Decimal('0')),  #for 'collectedInPeriod'
                #aggregates for 'collectedByMethod'
                revenue_by_cash=Coalesce(Sum('amount', filter=Q(method='cash') & date_filter), Decimal('0')),
                revenue_by_card=Coalesce(Sum('amount', filter=Q(method='card') & date_filter), Decimal('0')),
                revenue_by_bank=Coalesce(Sum('amount', filter=Q(method='bank_transfer') & date_filter), Decimal('0')),
                revenue_by_insurance=Coalesce(Sum('amount', filter=Q(method='insurance') & date_filter), Decimal('0')),
                revenue_by_mobWallet=Coalesce(Sum('amount', filter=Q(method='mobile_wallet') & date_filter), Decimal('0')),
                # currency=Max('currency')
            )

            #calculate total outstanding from bill/transaction totals
            totalOutstanding = bills_aggregates['total_billed'] - transactions_aggregates['total_revenue']
            totalOutstanding = Decimal(str(totalOutstanding)) if (totalOutstanding > 0) else Decimal('0')

            #Add computed revenue data 
            data['revenue'] = {
                'billedInPeriod': bills_aggregates['billed_in_range'],
                'collectedInPeriod': transactions_aggregates['revenue_in_range'],
                'totalOutstanding': totalOutstanding, 
                # 'currency': transactions_aggregates['currency']
                'collectedByMethod': {
                    'cash': transactions_aggregates['revenue_by_cash'],
                    'card': transactions_aggregates['revenue_by_card'],
                    'bank_transfer': transactions_aggregates['revenue_by_bank'],
                    'insurance': transactions_aggregates['revenue_by_insurance'],
                    'mobile_wallet': transactions_aggregates['revenue_by_mobWallet'],
                }
            }


        #Serialize data to return response
        serializer = self.get_serializer(data)

        #return response
        return Response(serializer.data, status=status.HTTP_200_OK)


#Dashboard Appointments Today API View
@extend_schema(tags=['Dashboard'])
class DashboardAppointmentTodayAPIView(FieldsTranslationMixin, FilterByBranchMixin, generics.ListAPIView):  #No finalize response mixin
    serializer_class = DashboardAppointmentTodaySerializer
    permission_classes = [SystemUserPermissions]
    required_permission = 'view.calendar'
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
class DashboardOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView): 
    serializer_class = DashboardOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
