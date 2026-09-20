from utils.base_views import *
from users.models import User
from django.http import Http404
from django.db.models import Count
from utils.validators import validate_uuid
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from users.utils import get_required_permission
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from utils.mixins import BranchToSerializerMixin
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from patients.models import Patient, InboundReferral, OutboundReferral
from users.permissions import SystemUserPermissions, PatientDataPermissions
from patients.filters import InboundReferralsFilter, OutboundReferralsFilter
from utils.swagger_utils import extend_schema, OpenApiParameter, OpenApiTypes
from patients.serializers.referrals import (InboundReferralSerializer, CreateInboundReferralSerializer,
                                            UpdateInboundReferralSerializer, OutboundReferralSerializer,
                                            CreateOutboundReferralSerializer, UpdateOutboundReferralSerializer,
                                            PatchOutboundStatusSerializer, ReferralsOptionsSerializer)


#REFERRALS API VIEWS

#INBOUND REFERRALS
#List/Create inbound referrals API view 
@extend_schema(tags=['Referrals'])
class ListCreateInboundReferralsAPIView(FilterListCreateAPIView):
    permission_classes = [SystemUserPermissions]
    ordering = ['branch__name', 'name']  #default order of fields
    ordering_fields = ['speciality', 'createdAt']
    search_fields = ['name', 'clinic', 'speciality', 'notes']  #search fields
    filterset_class = InboundReferralsFilter  #filters by status, branch, and insurance provider
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('referrals', request, self)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        #fetch inbound referrals queryset
        referrals = InboundReferral.objects.select_related('branch', 'referredByUser').all()
        
        if self.request.method == 'POST':
            return referrals
        
        #Annotate patient count
        referrals = referrals.annotate(patientCount=Count('referred_patients')).all()

        #Filter queryset for list by role
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return referrals
        
        elif getattr(user, 'role', None) == 'dentist' or\
         self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(referrals)
        else:
            return referrals.none()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return InboundReferralSerializer
        else:
            return CreateInboundReferralSerializer
        

#Retrieve/update/delete inbound referral API view
@extend_schema(tags=['Referrals'])
class RetrieveUpdateDeleteInboundReferralAPIView(RetrieveUpdateDeleteAPIView):
    queryset =  InboundReferral.objects.select_related('branch', 'referredByUser')\
        .annotate(patientCount=Count('referred_patients')).all()
    permission_classes = [SystemUserPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #Determine required permission
        self.required_permission = get_required_permission('referrals', request, self)
        super().initial(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return UpdateInboundReferralSerializer
        else:
            return InboundReferralSerializer

    def destroy(self, request, *args, **kwargs):
        referral = self.get_object()
        #soft delete referral
        InboundReferral.objects.delete_referral(user=request.user, referral=referral)
        return Response({}, status=status.HTTP_204_NO_CONTENT)


###################


#OUTBOUND REFERRALS
#List/Create outbound referrals API view -- general
@extend_schema(tags=['Referrals'])
class ListOutboundReferralsAllAPIView(FilterListCreateAPIView):
    serializer_class = OutboundReferralSerializer
    permission_classes = [PatientDataPermissions]
    ordering = ['-updatedAt']
    ordering_fields = ['status', 'createdAt', 'updatedAt']
    search_fields = ['name', 'patient__name', 'status', 'notes']
    filterset_class = OutboundReferralsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('referrals', request, self)
        super().initial(request, *args, **kwargs)
    
    def get_queryset(self):
        #fetch outbound referrals queryset
        referrals = OutboundReferral.objects.select_related(
            'patient', 'branch', 'referredToUser', 'referredToEntity'
        ).all()

        #Filter queryset for list by role
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return referrals
        elif getattr(user, 'role', None) == 'dentist':
            return referrals.filter(patient__doctor=user)        
        elif self.required_permission in getattr(user, 'userPermissions', []):
            return self.filter_by_branch(referrals)
        else:
            return referrals.none()
    

#List/Create outbound referrals API view -- scooped by `patient`
@extend_schema(tags=['Referrals'])
class ListCreateOutboundReferralsAPIView(ListCreateAPIView):
    permission_classes = [PatientDataPermissions]
    ordering = ['-updatedAt']
    ordering_fields = ['status', 'createdAt', 'updatedAt']
    search_fields = ['name', 'patient__name', 'status', 'notes']
    filterset_class = OutboundReferralsFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, CustomOrderingFilter]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('referrals', request, self)
        super().initial(request, *args, **kwargs)
    
    def get_queryset(self):
        #validate patient
        try:
            patient = Patient.objects.only('id').get(id=self.kwargs['id'])
        except (Patient.DoesNotExist, Http404):
            raise NotFound(_('The requested patient was not found or does not exist.'))
        
        #return patient's outbound referrals record only
        return patient.patient_outbound_referrals.select_related(
            'branch', 'referredToUser', 'referredToEntity'
        ).all()

    def get_serializer_context(self): 
        serializer_context = super().get_serializer_context()
        if self.request.method == 'POST':
            #add patient id from url to create serializer 
            serializer_context['patient_id'] = self.kwargs['id']
        return serializer_context


#Retrieve/update/delete outbound
@extend_schema(tags=['Referrals'])
class RetrieveUpdateDeleteOutboundReferralsAPIView(RetrieveUpdateDeleteAPIView):
    permission_classes = [PatientDataPermissions]
    lookup_url_kwarg = 'referralId'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission
        self.required_permission = get_required_permission('referrals', request, self)
        super().initial(request, *args, **kwargs)
    
    def get_object(self):
        try:
            obj = OutboundReferral.objects.get(id=self.kwargs['referralId'], patient_id=self.kwargs['id'])
        except (OutboundReferral.DoesNotExist, Http404):
            raise NotFound(_('The requested patient referral record was not found or does not exist.'))

        #check object permission and return referral object
        self.check_object_permissions(self.request, obj)
        return obj
    
    def get_serializer_class(self):
        req_method = self.request.method
        if req_method == 'PUT':
            return UpdateOutboundReferralSerializer
        elif req_method == 'PATCH':
            return PatchOutboundStatusSerializer
        else:
            return OutboundReferralSerializer
    

###################


#OPTIONS
#API View for serving optional choices data 
@extend_schema(
    tags=['Referrals'],
    parameters=[
        OpenApiParameter('branchId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('doctorId', OpenApiTypes.UUID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('lang', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
    ]
)
class RetrieveReferralsOptionsAPIView(BranchToSerializerMixin, generics.GenericAPIView):
    serializer_class = ReferralsOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()  #get branchId and add others
        doctorId = validate_uuid(self.request.query_params.get('doctorId'), 'doctorId')

        if doctorId:
            if not User.objects.filter(id=doctorId, role__in=['dentist', 'admin']).exists():
                raise ValidationError({'doctorId': _("User not found or not registered as a doctor.")})
            
        #add doctor to serializer context
        context['doctorId'] = doctorId
        return context

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)

