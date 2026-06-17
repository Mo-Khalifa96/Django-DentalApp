
import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status


pytestmark = pytest.mark.django_db


class TestDashboardAPI:
    def test_dashboard_stats_returns_expected_aggregates(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
        visit_factory,
        treatment_plan_factory,
        inventory_factory,
    ):
        today = timezone.localdate()
        days_until_saturday = (5 - today.weekday() + 7) % 7
        starting_saturday = today + timedelta(days=days_until_saturday)
        weekly_appointment_date = (
            starting_saturday if starting_saturday != today else starting_saturday + timedelta(days=1)
        )

        patient_today = patient_factory(doctor=dentist_user)
        patient_for_week = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()

        appointment_factory(
            patient=patient_today,
            doctor=dentist_user,
            procedure=procedure,
            date=today,
        )
        appointment_factory(
            patient=patient_for_week,
            doctor=dentist_user,
            procedure=procedure,
            date=weekly_appointment_date,
        )
        visit_factory(
            patient=patient_today,
            doctor=dentist_user,
            date=today,
            paid='400.00',
        )
        treatment_plan_factory(
            patient=patient_today,
            procedure=procedure,
            doctor=dentist_user,
            status='pending',
        )
        treatment_plan_factory(
            patient=patient_for_week,
            procedure=procedure,
            doctor=dentist_user,
            status='completed',
        )
        inventory_factory(currentStock=1, minStock=5)
        inventory_factory(currentStock=10, minStock=5)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse('dashboard_stats'))

        expected_appointments_this_week = 2 if starting_saturday == today else 1

        assert response.status_code == status.HTTP_200_OK
        
        response_data = response.data['data']
        assert response_data['patientsTotal'] == 2
        assert response_data['patientsNew'] == 2
        assert response_data['appointmentsCount'] == 1
        assert response_data['appointmentsCompleted'] == 0
        assert response_data['revenue'] == 0.0
        assert response_data['outstanding'] == 0.0



    def test_dashboard_stats_rejects_inverted_date_range(self, api_client, admin_user):
        '''Validates dateRange choices: [today, week, month].'''
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(
            reverse('dashboard_stats'),
            {'dateRange': 'invalid_range'},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


    def test_dashboard_appointments_today_filters_by_authenticated_dentist(
        self,
        api_client,
        dentist_user,
        other_dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
    ):
        today = timezone.localdate()
        procedure = procedure_factory()
        visible_patient = patient_factory(doctor=dentist_user)
        hidden_patient = patient_factory(doctor=other_dentist_user)

        visible_appointment = appointment_factory(
            patient=visible_patient,
            doctor=dentist_user,
            procedure=procedure,
            date=today,
        )
        appointment_factory(
            patient=hidden_patient,
            doctor=other_dentist_user,
            procedure=procedure,
            date=today,
        )
        appointment_factory(
            patient=visible_patient,
            doctor=dentist_user,
            procedure=procedure,
            date=today + timedelta(days=1),
        )

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse('dashboard_appointments_today'))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['metadata']['userPermissions']['view.appointments'] is True
        # ListAPIView returns a paginated list; appointments are under `data`.
        appointments = response.data['data']
        assert [item['id'] for item in appointments] == [str(visible_appointment.id)]

