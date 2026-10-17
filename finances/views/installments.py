from decimal import Decimal
from utils.base_views import *
from users.models import User
from django.http import Http404
from django.db import transaction
from django.utils import timezone
from patients.models import TreatmentPlan
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from finances.filters import InstallmentsFilter
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from users.utils import get_required_permission
from utils.mixins import BranchToSerializerMixin
from users.permissions import PatientDataPermissions
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from utils.exceptions import InstallmentPlanInProgressError
from django_filters.rest_framework import DjangoFilterBackend
from finances.models import InstallmentPlan, Installment, Transaction
from django.db.models import Q, F, Prefetch, Case, When, Value, CharField
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from finances.serializers.installments import (InstallmentPlanSerializer, RetrievePatientInstallmentPlanSerializer, 
                                               GenerateInstallmentPlanSerializer, UpdateInstallmentPlanSerializer, 
                                               AutogenerateInstallmentsBillSerializer, CreateInstallmentTransactionSerializer,
                                               RetrieveInstallmentTransactionSerializer, UpdateInstallmentTransactionSerializer,
                                               InstallmentsOptionsSerializer)


#INSTALLMENTS API VIEWS
#Create installment plan API view
# POST api/patients/{id}/treatment-plans/{treatmentId}/installments/generate/ --> GenerateInstallmentPlanSerializer
@extend_schema(tags=['Installments'])
class GenerateInstallmentPlanAPIView(CreateAPIView):
    serializer_class = GenerateInstallmentPlanSerializer
    permission_classes = [PatientDataPermissions]

    def initial(self, request, *args, **kwargs):
        #determine required permission
        if getattr(request.user, 'role', None) == 'dentist':
            self.required_permission = 'create.treatment'
        else:
            self.required_permission = 'create.installments'
            
        super().initial(request, *args, **kwargs)

    def get_treatment(self):
        try:
            treatment = TreatmentPlan.objects.select_related('patient')\
             .prefetch_related('installment_plan')\
             .get(
                id=self.kwargs['treatmentId'],
                patient_id=self.kwargs['id']
            )
        except (TreatmentPlan.DoesNotExist, Http404):
            raise NotFound(_('Treatment plan was not found or does not exist.'))

        #check object permission and return treatment
        self.check_object_permissions(self.request, treatment)
        return treatment
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method == 'POST':
            context['treatment'] = self.get_treatment()
        return context


#Autogenerate bill for installment plan API view (general/patient-scooped)
# POST api/installments/{id}/autogenerate-bill/ --> AutogenerateInstallmentsBillSerializer
# POST api/patients/{id}/treatment-plans/{treatmentId}/installments/autogenerate-bill/ --> AutogenerateInstallmentsBillSerializer
@extend_schema(tags=['Installments'])
class AutogenerateInstallmentsBillAPIView(CreateAPIView):
    serializer_class = AutogenerateInstallmentsBillSerializer
    permission_classes = [PatientDataPermissions]

    def initial(self, request, *args, **kwargs):
        #determine required permission
        if 'treatment-plans' in request.path:
            self.required_permission = 'create.treatment'
        else:
            self.required_permission = 'create.bill'
            
        super().initial(request, *args, **kwargs)

    def get_installment_plan(self):
        path = self.request.path

        try:
            if 'treatment-plans' in path:
                error_detail = _("The current treatment plan doesn't have an installment plan to generate a bill for. "
                                 "The installment plan might be deleted or does not exist. "
                                 "If you believe this not to be the case, please contact the support team immediately.")
                
                #fetch installment plan
                plan = InstallmentPlan.objects.select_related('treatment', 'treatment__patient')\
                 .prefetch_related('bill').get(
                    treatment_id=self.kwargs.get('treatmentId'), 
                    treatment__patient_id=self.kwargs.get('id')
                )
            else:
                error_detail = _('Installment plan was not found or does not exist.')
                
                #fetch installment plan
                plan = InstallmentPlan.objects.select_related('treatment', 'treatment__patient')\
                 .prefetch_related('bill').get(
                    id=self.kwargs.get('id')
                )

        except (InstallmentPlan.DoesNotExist, Http404):
            raise NotFound(error_detail)

        #check object permission and return installment plan
        self.check_object_permissions(self.request, plan)
        return plan
    
    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        if self.request.method == 'POST':
            #pass installment plan to bill serializer
            serializer_context['installment_plan'] = self.get_installment_plan()
        return serializer_context
    

#List installment plans/installments API view (general)
# GET api/installments/ --> InstallmentPlanSerializer
@extend_schema(tags=['Installments'])
class ListInstallmentPlansAPIView(FilterListAPIView):
    serializer_class = InstallmentPlanSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'view.installments'
    ordering = ['-updatedAt']
    ordering_fields = ['treatment__patient__name', 'branch__name', 'totalAmount', 
                       'totalPaid', 'status', 'createdAt', 'updatedAt']
    search_fields = ['treatment__patient__name', 'treatment__title', 'branch__name']
    filterset_class = InstallmentsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def get_queryset(self):
        #prepare queryset
        #annotate nested installments with their current status
        installments_qs = Installment.objects.select_related('transaction').annotate(
            status=Case(
                When(paidAt__isnull=False, then=Value('paid')),
                When(dueDate__lt=timezone.localdate(timezone.now()), then=Value('overdue')),
                default=Value('pending'),
                output_field=CharField()
            )
        )
        
        installment_plans = InstallmentPlan.objects.select_related('treatment', 'branch')\
         .prefetch_related('bill', Prefetch('installments', queryset=installments_qs))\
         .annotate(
             status=Case(
                 When(Q(totalPaid__isnull=True) | Q(totalPaid=Decimal('0')), then=Value('pending')),
                 When(totalPaid__gte=F('totalAmount'), then=Value('completed')),
                 When(totalPaid__lt=F('totalAmount'), then=Value('partial')),
                default=Value('pending'),
                output_field=CharField()
             )
         )

        #get current user 
        user = self.request.user

        #filter queryset by role or branch
        if getattr(user, 'role', None) == 'admin':
            return installment_plans        
        elif getattr(user, 'role', None) == 'dentist':
            return installment_plans.filter(treatment__doctor=user)
        elif self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(installment_plans)
        else:
            return installment_plans.none()
    
    def paginate_queryset(self, queryset):
        self.paginator.page_size = 15
        return super().paginate_queryset(queryset)



#Retrieve/Update/Delete patient's installment plan API view
# GET api/patients/{id}/treatment-plans/{treatmentId}/installments/ --> RetrievePatientInstallmentPlanSerializer
# PATCH api/patients/{id}/treatment-plans/{treatmentId}/installments/ --> UpdateInstallmentPlanSerializer
# DELETE api/patients/{id}/treatment-plans/{treatmentId}/installments/ --> None
@extend_schema(tags=['Installments'])
class RetrieveUpdateDeletePatientInstallmentPlanAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    # lookup_url_kwarg = 'treatmentId'
    # lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('treatment-plans', request, self)
        super().initial(request, *args, **kwargs)

    def get_object(self):
        try:
            obj = InstallmentPlan.objects.select_related('treatment', 'branch')\
                .prefetch_related('bill', 'installments', 'installments__transaction')\
                .get(treatment_id=self.kwargs.get('treatmentId'), treatment__patient_id=self.kwargs.get('id'))

        except (InstallmentPlan.DoesNotExist, Http404):
            raise NotFound(_('The requested installment plan was not found or does not exist.'))

        #check object permission and return installment plan
        self.check_object_permissions(self.request, obj)
        return obj

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return UpdateInstallmentPlanSerializer
        return RetrievePatientInstallmentPlanSerializer

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        #get bill object
        plan = self.get_object()
        
        #Check first if any installment has beeen paid
        if plan and plan.installments and plan.installments.filter(paidAt__isnull=False).exists():
            raise InstallmentPlanInProgressError(
                detail=_('This installment plan cannot be deleted because one or more installments have already been paid.')
            )

        #delete installment plan
        plan.delete()
        return Response({}, status=status.HTTP_204_NO_CONTENT)


#Update/Delete installment plan API view (general)
# PATCH api/installments/{id}/ --> UpdateInstallmentPlanSerializer
# DELETE api/installments/{id}/ --> None
@extend_schema(tags=['Installments'])
class UpdateDeleteInstallmentPlanAPIView(UpdateAPIView, DeleteAPIView):
    queryset = InstallmentPlan.objects.select_related('treatment', 'branch')\
                .prefetch_related('bill', 'installments', 'installments__transaction')
    serializer_class = UpdateInstallmentPlanSerializer
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        self.required_permission = get_required_permission('installments', request, self)
        super().initial(request, *args, **kwargs)

    # def get_serializer_class(self):
    #     if self.request.method == 'PATCH':
    #         return UpdateInstallmentPlanSerializer
    #     return RetrievePatientInstallmentPlanSerializer

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        #get bill object
        plan = self.get_object()
        
        #Check first if any installment has beeen paid
        if plan and plan.installments and plan.installments.filter(paidAt__isnull=False).exists(): 
            raise InstallmentPlanInProgressError(
                detail=_('This installment plan cannot be deleted because one or more installments have already been paid.')
            )

        #delete installment plan
        plan.delete()
        return Response({}, status=status.HTTP_204_NO_CONTENT)


#Create installment transaction API view
# POST api/installments/{id}/transactions/ --> CreateInstallmentTransactionSerializer
@extend_schema(tags=['Installments'])
class CreateInstallmentTransactionAPIView(CreateAPIView):
    serializer_class = CreateInstallmentTransactionSerializer
    permission_classes = [PatientDataPermissions]
    required_permission = 'create.transaction'

    def get_installment_plan(self):
        try:
            #fetch installment plan
            plan = InstallmentPlan.objects.select_related('treatment')\
                .prefetch_related(
                    'bill', 'bill__branch', 'bill__patient', 
                    'bill__patient__patient_insurance'
                ).get(
                    id=self.kwargs.get('id')
                )
            
        except (InstallmentPlan.DoesNotExist, Http404):
            raise NotFound(_('Installment plan was not found or does not exist.'))

        #check object permission and return installment plan
        self.check_object_permissions(self.request, plan)
        return plan
    
    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        if self.request.method == 'POST':
            #pass installment plan to bill serializer
            serializer_context['installment_plan'] = self.get_installment_plan()
        return serializer_context


#Retrieve/Update/Delete installment transaction API view
# GET api/installments/{id}/transactions/{transactionId}/ --> RetrieveInstallmentTransactionSerializer
# PUT api/installments/{id}/transactions/{transactionId}/ --> UpdateInstallmentTransactionSerializer
# DELETE api/installments/{id}/transactions/{transactionId}/ --> None
@extend_schema(tags=['Installments'])
class RetrieveUpdateDeleteInstallmentTransactionAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'transactionId'  #lookup field/keyword as defined on url
    lookup_field = 'id'  #model's lookup field

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('transactions', request, self)
        super().initial(request, *args, **kwargs)

    def get_installment_plan(self):
        try:
            #fetch installment plan
            plan = InstallmentPlan.objects.only('id').get(id=self.kwargs.get('id'))
            
        except (InstallmentPlan.DoesNotExist, Http404):
            raise NotFound(_('Installment plan was not found or does not exist.'))

        #check object permission and return installment plan
        self.check_object_permissions(self.request, plan)
        return plan
    
    def get_queryset(self):
        #get current plan from url and check perms
        plan = self.get_installment_plan()

        #admin gets all objects
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            #keep only transactions associated with the plan
            transactions = Transaction.all_objects.prefetch_related('installments')\
             .select_related('patient', 'bill', 'bill__installmentPlan', 'branch')\
             .filter(Q(bill__installmentPlan_id=plan.id) | Q(installments__installmentPlan_id=plan.id))\
             .distinct()
        else:
            transactions = Transaction.objects.prefetch_related('installments')\
             .select_related('patient', 'bill', 'bill__installmentPlan', 'branch')\
             .filter(Q(bill__installmentPlan_id=plan.id) | Q(installments__installmentPlan_id=plan.id))\
             .distinct()
        return transactions

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return UpdateInstallmentTransactionSerializer
        return RetrieveInstallmentTransactionSerializer

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        #get bill object
        transaction = self.get_object()

        #soft delete bill and return response
        Transaction.objects.delete_transaction(user=request.user, transaction=transaction)
        return Response({}, status=status.HTTP_204_NO_CONTENT)


#Retrieve installments options API view
# GET api/installments/options/ --> InstallmentsOptionsSerializer
@extend_schema(
    tags=['Installments'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('doctorId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('installmentPlanId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False)
    ]
)
class RetrieveInstallmentsOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = InstallmentsOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()  #get branchId and add others
        doctorId = validate_uuid(self.request.query_params.get('doctorId'), 'doctorId')
        installmentPlanId = validate_uuid(self.request.query_params.get('installmentPlanId'), 'installmentPlanId')

        if installmentPlanId:
            try:
                InstallmentPlan.objects.get(id=installmentPlanId)
            except (InstallmentPlan.DoesNotExist, Http404):
                raise ValidationError({'installmentPlanId': _('Installment plan was not found or does not exist.')})
        
        if doctorId:
            if not User.objects.filter(id=doctorId, role__in=['dentist', 'admin']).exists():
                raise ValidationError({'doctorId': _("User not found or not registered as a doctor.")})
            
        #add patient and doctor to serializer context   
        context['doctorId'] = doctorId
        context['installmentPlanId'] = installmentPlanId
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
