import pytest
from unittest.mock import Mock
from django.urls import reverse
from django.utils import timezone
from datetime import time, timedelta
from rest_framework import status
from services.models import Message
from patients.models import Appointment, Patient
from services.whatsapp.exceptions import WhatsAppAPIError


pytestmark = pytest.mark.django_db


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def message_factory():
    from services.models import Message

    def create_message(patient, appointment, **overrides):
        defaults = {
            'message': 'Appointment reminder',
            'status': 'queued',
        }
        defaults.update(overrides)
        return Message.objects.create(
            patient=patient,
            appointment=appointment,
            **defaults,
        )

    return create_message


# ─────────────────────────────────────────────────────────────────────────────
# Testing Class
# ─────────────────────────────────────────────────────────────────────────────

class TestAppointmentsAPI:
    def test_list_appointments_returns_paginated_results(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
    ):
        procedure = procedure_factory()
        patient = patient_factory(doctor=dentist_user)
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure)
        appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse('list_create_appointments'))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['pagination']['total'] == 2
        assert any(item['id'] == str(appointment.id) for item in response.data['data'])

    def test_dentist_only_sees_their_own_appointments(
        self,
        api_client,
        dentist_user,
        other_dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
    ):
        procedure = procedure_factory()
        patient_one = patient_factory(doctor=dentist_user)
        patient_two = patient_factory(doctor=other_dentist_user)
        visible = appointment_factory(patient=patient_one, doctor=dentist_user, procedure=procedure)
        appointment_factory(patient=patient_two, doctor=other_dentist_user, procedure=procedure)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse('list_create_appointments'))

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['data']] == [str(visible.id)]

    def test_create_appointment_for_existing_patient_assigns_doctor_and_next_appointment(
        self,
        api_client,
        receptionist_user,
        dentist_user,
        patient_factory,
        procedure_factory,
    ):
        patient = patient_factory(doctor=None)
        procedure = procedure_factory(name='Teeth Cleaning')
        appointment_date = timezone.localdate() + timedelta(days=2)
        payload = {
            'patientId': str(patient.id),
            'doctorId': str(dentist_user.id),
            'procedureId': str(procedure.id),
            'type': 'routine_checkup',
            'date': appointment_date.isoformat(),
            'startTime': '09:00:00',
            'endTime': '10:00:00',
            'room': 'Room A',
            'branchId': '',
        }

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(reverse('list_create_appointments'), payload, format='json')

        # Print DRF error for easier sync with updated serializer
        if response.status_code != status.HTTP_201_CREATED:
            print('DEBUG appointment create response:', response.status_code, response.json())

        assert response.status_code == status.HTTP_201_CREATED

        patient.refresh_from_db()
        created_appointment = Appointment.objects.get(id=response.data['data']['id'])
        assert patient.doctor == dentist_user
        assert patient.nextAppointment == appointment_date
        assert created_appointment.type == 'routine_checkup'

    def test_create_appointment_can_create_a_new_patient(
        self,
        api_client,
        receptionist_user,
        dentist_user,
        procedure_factory,
        branch
    ):
        procedure = procedure_factory(name='Initial Consultation')
        payload = {
            'is_newPatient': True,
            'newPatientDetails': {
                'name': 'New Booking Patient',
                'age': 28,
                'gender': 'Female',
                'countryCode': '20',
                'phone': '01055556666',
            },
            'doctorId': str(dentist_user.id),
            'procedureId': str(procedure.id),
            'type': 'routine_checkup',
            'date': (timezone.localdate() + timedelta(days=3)).isoformat(),
            'startTime': '11:00:00',
            'endTime': '12:00:00',
            'room': 'Room B',
            'branchId': str(branch.id)
        }

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(reverse('list_create_appointments'), payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED

        patient = Patient.objects.get(name='New Booking Patient')
        assert patient.doctor == dentist_user
        assert patient.patient_dentalchart.teeth
        assert Appointment.objects.filter(id=response.data['data']['id'], patient=patient).exists()

    def test_create_appointment_rejects_conflicting_time_slot(
        self,
        api_client,
        receptionist_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
        branch
    ):
        procedure = procedure_factory(name='Root Canal')
        patient = patient_factory(doctor=dentist_user)
        other_patient = patient_factory(doctor=dentist_user)
        appointment_date = timezone.localdate() + timedelta(days=1)
        appointment_factory(
            patient=patient,
            doctor=dentist_user,
            procedure=procedure,
            date=appointment_date,
            startTime=time(9, 0),
            endTime=time(10, 0),
        )
        payload = {
            'patientId': str(other_patient.id),
            'doctorId': str(dentist_user.id),
            'procedureId': str(procedure.id),
            'type': 'routine_checkup',
            'date': appointment_date.isoformat(),
            'startTime': '09:30:00',
            'endTime': '10:30:00',
            'room': 'Room C',
            'branchId': str(branch.id)
        }

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(reverse('list_create_appointments'), payload, format='json')

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data['error']['code'] == 'APPOINTMENT_CONFLICT'
        assert response.data['error']['conflictWith']['patientName'] == patient.name

    def test_retrieve_appointment_returns_patient_phone(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
    ):
        patient = patient_factory(doctor=dentist_user, phone='01012345678', countryCode='20')
        procedure = procedure_factory()
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(
            reverse('retrieve_update_cancel_appointment', kwargs={'id': appointment.id})
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['patientId'] == patient.id
        assert response.data['data']['patientPhone'] == '01012345678'

    def test_cancel_appointment_updates_status_and_reason(
        self,
        api_client,
        receptionist_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure)

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.delete(
            reverse('retrieve_update_cancel_appointment', kwargs={'id': appointment.id}),
            {'reason': 'Patient requested a reschedule.'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        appointment.refresh_from_db()
        assert appointment.status == 'cancelled'
        assert appointment.notes == 'Patient requested a reschedule.'
        assert response.data['data']['success'] is True

    def test_appointment_options_returns_patients_doctors_and_procedures(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
    ):
        patient = patient_factory(name='Options Patient', doctor=dentist_user)
        procedure = procedure_factory(name='Whitening')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse('appointments_options'))

        assert response.status_code == status.HTTP_200_OK
        assert {'patientId': patient.id, 'name': patient.name} in response.data['patientChoices']
        assert {'doctorId': dentist_user.id, 'name': dentist_user.name} in response.data['doctorChoices']
        #rrent appointment options serializer exposes statusChoices as list of dicts
        assert {'value': 'cancelled', 'label': 'cancelled'} in response.data['statusChoices']


class TestWhatsAppEndpoints:
    def test_send_whatsapp_message_creates_message_and_calls_sender(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
        monkeypatch,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure)
        sender = Mock()
        monkeypatch.setattr('services.views.send_twilio_message_task', sender)

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse('send_whatsapp_reminder'),
            {
                'patientId': str(patient.id),
                'appointmentId': str(appointment.id),
                'message': 'Your appointment is tomorrow.',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        sender.assert_called_once()
        message = Message.objects.get(id=response.data['data']['messageId'])
        assert message.status == 'queued'
        assert message.templateName == 'custom_message_english'

    def test_send_whatsapp_message_falls_back_to_pending_on_api_error(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
        monkeypatch,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure)

        def raise_whatsapp_error(*args, **kwargs):
            raise WhatsAppAPIError('Temporary provider issue', error_code='TEMP_ERROR')

        monkeypatch.setattr(
            'services.views.send_twilio_message_task',
            raise_whatsapp_error,
        )
        # async_task is no longer imported from patients.views.appointments
        #send_twilio_message_task is called directly in the serializer/view)
        monkeypatch.setattr('services.views.async_task', Mock(), raising=False)

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse('send_whatsapp_reminder'),
            {
                'patientId': str(patient.id),
                'appointmentId': str(appointment.id),
                'message': 'Resending your reminder.',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        message = Message.objects.get(id=response.data['data']['messageId'])
        assert message.status == 'pending'

    def test_webhook_verification_returns_challenge(self, api_client):
        response = api_client.get(
            reverse('whatsapp_webhook'),
            {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'test-webhook-token',
                'hub.challenge': 'challenge-123',
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content.decode() == 'challenge-123'

    def test_webhook_post_updates_message_status(
        self,
        api_client,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
        message_factory,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure)
        message = message_factory(
            patient=patient,
            appointment=appointment,
            providerMessageId='provider-123',
            status='sent',
        )

        response = api_client.post(
            reverse('whatsapp_webhook'),
            {
                'entry': [
                    {
                        'changes': [
                            {
                                'value': {
                                    'statuses': [
                                        {'id': 'provider-123', 'status': 'delivered'}
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        message.refresh_from_db()
        assert message.status == 'delivered'
        assert response.json() == {'status': 'ok'}
