from utils.base_views import *
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.response import Response
from utils.swagger_utils import extend_schema
from patients.models import Patient, PerioExam
from django.shortcuts import get_object_or_404
from utils.filters import CustomOrderingFilter
from rest_framework.filters import SearchFilter
from users.utils import get_required_permission
from utils.exceptions import PerioExamLockedError
from rest_framework.permissions import IsAuthenticated
from users.permissions import UnrestrictedObjectPermissions
from patients.docs import get_list_create_perio_exams_schema, get_retrieve_update_perio_exam_schema
from patients.serializers.perio_exams import (ListPerioExamsSummarySerializer, RetrievePerioExamSerializer,
                                              CreatePerioExamSerializer, UpdatePerioExamSerializer, 
                                              PerioExamOptionsSerializer)


#Initialize schemas periodontal chart views
# perio_exam_view_schema = get_perio_exam_schema()
list_create_perio_exams_schema = get_list_create_perio_exams_schema()
retrieve_update_perio_exam_schema = get_retrieve_update_perio_exam_schema()


#PATIENT PERIODONTAL CHART API VIEWS
#List/Create patient perio exams API view
@list_create_perio_exams_schema
class ListCreatePerioExamsAPIView(ListCreateAPIView):
    permission_classes = [UnrestrictedObjectPermissions]
    ordering = ['-examinedAt', '-createdAt']
    ordering_fields = ['examinedAt']
    search_fields = ['examinedByName', 'notes']
    filter_backends = [SearchFilter, CustomOrderingFilter]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission 
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)

    def get_patient(self):
        #fetch patient from url
        patient = get_object_or_404(Patient.objects.only('id').all(), id=self.kwargs.get('id'))
        #check object permission and return patient object
        # self.check_object_permissions(self.request, patient) -- may be a different doctor on a different branch
        return patient

    def get_queryset(self):
        #Get current patient
        patient = self.get_patient()

        #Get patient's perio exams
        perio_exams = PerioExam.objects.select_related('examinedBy').filter(patient_id=patient.id)

        #Check user permission
        user = self.request.user
        if getattr(user, 'role', None) in ('admin', 'doctor') or\
         self.required_permission in getattr(user, 'userPermissions', []):
            return perio_exams
        else:
            return perio_exams.none()

    def paginate_queryset(self, queryset):
        self.paginator.page_size = 20
        return super().paginate_queryset(queryset)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreatePerioExamSerializer
        return ListPerioExamsSummarySerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method == 'POST':
            patient = self.get_patient()
            context['patient_id'] = patient.id  #pass patient id
        return context

#Retrieve/Update perio exam API view
@retrieve_update_perio_exam_schema
class RetrieveUpdatePerioExamAPIView(RetrieveUpdateAPIView):
    permission_classes = [UnrestrictedObjectPermissions]
    lookup_url_kwarg = 'id'
    lookup_field = 'id'

    def initial(self, request, *args, **kwargs):
        #determine required permission 
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)

    def get_patient(self):
        #fetch patient from url
        patient = get_object_or_404(Patient.objects.only('id').all(), id=self.kwargs.get('id'))
        # self.check_object_permissions(self.request, patient) -- may be a different doctor on a different branch
        return patient
    
    def get_object(self):
        #retrieve perio exam
        patient = self.get_patient()
        return get_object_or_404(PerioExam.objects.filter(patient_id=patient.id),
                                 id=self.kwargs.get('examId'))

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return UpdatePerioExamSerializer
        return RetrievePerioExamSerializer

def update(self, request, *args, **kwargs):
    #get current instance
    instance = self.get_object()

    #validate if the exam is locked (updating on a different date)
    if instance.examinedAt != timezone.localdate(timezone.now()):
        raise PerioExamLockedError()
    
    #call parent update() to initiate the normal update flow
    return super().update(request, *args, **kwargs)

#API View for serving optional choices data 
@extend_schema(tags=['Periodontal Chart'])
class RetrievePerioExamOptionsAPIView(generics.GenericAPIView):
    serializer_class = PerioExamOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)
