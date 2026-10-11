from utils.base_views import *
from patients.models import Patient
from rest_framework import status, generics
from rest_framework.response import Response
from utils.swagger_utils import extend_schema
from users.utils import get_required_permission
from patients.docs import get_dentalchart_schema
from users.permissions import PatientDataPermissions
from rest_framework.permissions import IsAuthenticated
from patients.serializers.dental_chart import DentalChartSerializer, DentalChartOptionsSerializer



#Initialize schema for retrieving patient dental chart
dentalchart_view_schema = get_dentalchart_schema()


#PATIENT DENTAL CHART API VIEWS 
#Retrieve/update patient dental chart API view
@dentalchart_view_schema
class RetrieveUpdateDentalChartAPIView(RetrieveUpdateAPIView):
    queryset = Patient.objects.prefetch_related('patient_dentalchart').all()
    serializer_class = DentalChartSerializer
    permission_classes = [PatientDataPermissions]
    lookup_field = 'id'
    lookup_url_kwarg = 'id'

    def get_object(self):
        #return patient's dental chart instance
        patient = super().get_object()
        return patient.patient_dentalchart

    def initial(self, request, *args, **kwargs):
        #determine required permission 
        # self.required_permission = 'view.patientDetail' if request.method == 'GET' else 'update.patient'
        self.required_permission = get_required_permission('patients', request, self)
        super().initial(request, *args, **kwargs)


#API view for serving optional choices data 
@extend_schema(tags=['Dental Chart'])
class RetrieveDentalChartOptionsAPIView(generics.GenericAPIView):
    serializer_class = DentalChartOptionsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(instance={}).data, status=status.HTTP_200_OK)

