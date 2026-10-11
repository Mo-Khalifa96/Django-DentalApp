from django.urls import path
from patients.views.visits import ListCreateVisitsAPIView, UploadXRayAPIView, RetrieveVisitsOptionsAPIView
from patients.views.patient_recalls import (ListCreatePatientRecallsAPIView, UpdateDeletePatientRecallAPIView, 
                                            RetrievePatientRecallsOptionsAPIView)
from patients.views.appointments import (ListCreateAppointmentsAPIView, RetrieveUpdateCancelAppointmentAPIView, 
                                         RetrieveAppointmentOptionsAPIView)
from patients.views.patient_insurance import (ListPatientCoveragePlansAPIView, CreateRetrieveUpdatePatientCoverageAPIView,
                                              PatientCoverageStatisticsAPIView, RetrievePatientCoverageOptionsAPIView)
from patients.views.treatments import (ListCreateTreatmentPlansAPIView, RetrieveUpdateDeleteTreatmentPlanAPIView,
                                      LookupTreatmentPlanAPIView, RetrieveTreatmentPlansOptionsAPIView)
from patients.views.dental_chart import (RetrieveUpdateDentalChartAPIView, RetrieveDentalChartOptionsAPIView)
from patients.views.perio_exams import (ListCreatePerioExamsAPIView, RetrieveUpdatePerioExamAPIView,
                                        RetrievePerioExamOptionsAPIView)
from patients.views.patients import (ListCreatePatientsAPIView, RetrieveUpdateDeletePatientAPIView,
                                     UploadDocumentAPIView, DeleteFileAPIView, RetrievePatientsOptionsAPIView)
from patients.views.referrals import (ListCreateInboundReferralsAPIView, RetrieveUpdateDeleteInboundReferralAPIView,
                                      ListOutboundReferralsAllAPIView, ListCreateOutboundReferralsAPIView,
                                      RetrieveUpdateDeleteOutboundReferralsAPIView, RetrieveReferralsOptionsAPIView)

#Url patterns
urlpatterns = [
    #Patients urls 
    path('patients/', ListCreatePatientsAPIView.as_view(), name='list_create_patients'),
    path('patients/<uuid:id>/', RetrieveUpdateDeletePatientAPIView.as_view(), name='retrieve_update_delete_patient'),
    path('patients/options/', RetrievePatientsOptionsAPIView.as_view(), name='patients_options'),
    #url for document uploads (optional)
    path('patients/<uuid:id>/documents/upload/', UploadDocumentAPIView.as_view(), name='upload_patient_document'),
    
    #Patient dental chart urls
    path('patients/<uuid:id>/dental-chart/', RetrieveUpdateDentalChartAPIView.as_view(), name='retrieve_update_dentalchart'),
    path('dental-chart/options/', RetrieveDentalChartOptionsAPIView.as_view(), name='dentalchart_options'),

    #Patient periodontal chart urls 
    path('patients/<uuid:id>/perio-charts/', ListCreatePerioExamsAPIView.as_view(), name='list_create_perio_exams'),
    path('patients/<uuid:id>/perio-charts/<uuid:examId>/', 
            RetrieveUpdatePerioExamAPIView.as_view(
                http_method_names=['get', 'put', 'options']
            ), name='retrieve_update_perio_exam'),
    path('perio-charts/options/', RetrievePerioExamOptionsAPIView.as_view(), name='perio_exams_options'),

    #Patient Visits urls
    path('patients/<uuid:id>/visits/', ListCreateVisitsAPIView.as_view(), name='list_create_visits'),
    path('patients/visits/options/', RetrieveVisitsOptionsAPIView.as_view(), name='visits_options'),
    #url for xray uploads (optional)
    path('patients/visits/<uuid:visitId>/xrays/upload/', UploadXRayAPIView.as_view(), name='upload_xray_image'),

    #Delete patient file url
    path('patients/files/delete/', DeleteFileAPIView.as_view(), name='delete_patient_file'),

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

    #Patient insurance coverage urls
    path('insurance/coverage/', ListPatientCoveragePlansAPIView.as_view(), name='list_patient_coverages'),
    path('insurance/coverage/<uuid:patientId>/', CreateRetrieveUpdatePatientCoverageAPIView.as_view(), name='create_retrieve_update_coverage'),
    path('insurance/coverage/summary/', PatientCoverageStatisticsAPIView.as_view(), name='patient_coverage_stats'),
    path('insurance/coverage/options/', RetrievePatientCoverageOptionsAPIView.as_view(), name='patient_coverage_options'),

    #Patient recalls urls 
    path('recalls/', ListCreatePatientRecallsAPIView.as_view(), name='list_create_patient_recalls'),
    path('recalls/<uuid:id>/', UpdateDeletePatientRecallAPIView.as_view(
            http_method_names=['patch', 'delete', 'options']
        ), name='update_delete_patient_recall'),
    path('recalls/options/', RetrievePatientRecallsOptionsAPIView.as_view(), name='patient_recalls_options'),

    #Referrals urls
    path('referrals/', ListCreateInboundReferralsAPIView.as_view(), name='list_create_inbound_referrals'),
    path('referrals/outbound/', ListOutboundReferralsAllAPIView.as_view(), name='list_outbound_referrals_all'),
    path('referrals/<uuid:id>/', RetrieveUpdateDeleteInboundReferralAPIView.as_view(
            http_method_names=['get', 'put', 'delete', 'options']
        ), name='retrieve_update_delete_inbound_referral'),
    path('patients/<uuid:id>/referrals-out/', ListCreateOutboundReferralsAPIView.as_view(), name='list_create_outbound_referrals'),
    path('patients/<uuid:id>/referrals-out/<uuid:referralId>/', RetrieveUpdateDeleteOutboundReferralsAPIView.as_view(), name='retrieve_update_delete_outbound_referral'),
    path('referrals/options/', RetrieveReferralsOptionsAPIView.as_view(), name='referrals_options')
]
