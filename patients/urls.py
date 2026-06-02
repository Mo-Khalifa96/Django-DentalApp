from django.urls import path
from patients.views.visits import ListCreateVisitsAPIView, RetrieveVisitsOptionsAPIView
from patients.views.patient_recalls import (ListCreatePatientRecallsAPIView, UpdateDeletePatientRecallAPIView, 
                                            RetrievePatientRecallsOptionsAPIView)
from patients.views.appointments import (ListCreateAppointmentsAPIView, RetrieveUpdateCancelAppointmentAPIView, 
                                         RetrieveAppointmentOptionsAPIView)
from patients.views.treatments import (ListCreateTreatmentPlansAPIView, RetrieveUpdateDeleteTreatmentPlanAPIView,
                                      LookupTreatmentPlanAPIView, RetrieveTreatmentPlansOptionsAPIView)
from patients.views.patients import (ListCreatePatientsAPIView, RetrieveUpdateDeletePatientAPIView,
                                     RetrieveUpdateDentalChartAPIView, RetrievePatientsOptionsAPIView, 
                                     RetrieveDentalChartOptionsAPIView)

#Url patterns
urlpatterns = [
    #Patients urls 
    path('patients/', ListCreatePatientsAPIView.as_view(), name='list_create_patients'),
    path('patients/<uuid:id>/', RetrieveUpdateDeletePatientAPIView.as_view(), name='retrieve_update_delete_patient'),
    path('patients/options/', RetrievePatientsOptionsAPIView.as_view(), name='patients_options'),
    
    #Patient dental chart urls
    path('patients/<uuid:id>/dental-chart/', RetrieveUpdateDentalChartAPIView.as_view(), name='retrieve_update_dentalchart'),
    path('dental-chart/options/', RetrieveDentalChartOptionsAPIView.as_view(), name='dentalchart_options'),

    #Patient Visits urls
    path('patients/<uuid:id>/visits/', ListCreateVisitsAPIView.as_view(), name='list_create_visits'),
    path('patients/visits/options/', RetrieveVisitsOptionsAPIView.as_view(), name='visits_options'),

    #Appointments urls 
    path('appointments/', ListCreateAppointmentsAPIView.as_view(), name='list_create_appointments'),
    path('appointments/<uuid:id>/', RetrieveUpdateCancelAppointmentAPIView.as_view(), name='retrieve_update_cancel_appointment'),
    path('appointments/options/', RetrieveAppointmentOptionsAPIView.as_view(), name='appointments_options'),

    #Treatment plans urls 
    path('patients/<uuid:id>/treatment-plans/', ListCreateTreatmentPlansAPIView.as_view(), name='list_create_treatments'),
    path('patients/<uuid:id>/treatment-plans/<uuid:treatmentId>/', 
            RetrieveUpdateDeleteTreatmentPlanAPIView.as_view(
                http_method_names=['get', 'put', 'delete', 'options']
            ), name='retrieve_update_delete_treatment'),
    path('treatment-plans/<uuid:id>/', LookupTreatmentPlanAPIView.as_view(), name='lookup_single_treatmentplan'),
    path('treatment-plans/options/', RetrieveTreatmentPlansOptionsAPIView.as_view(), name='treatment_plans_options'),

    #Patient recalls urls 
    path('recalls/', ListCreatePatientRecallsAPIView.as_view(), name='list_create_patient_recals'),
    path('recalls/<uuid:id>/', UpdateDeletePatientRecallAPIView.as_view(
            http_method_names=['patch', 'delete', 'options']
        ), name='update_delete_patient_recall'),
    path('recalls/options/', RetrievePatientRecallsOptionsAPIView.as_view(), name='patient_recalls_options'),
]
