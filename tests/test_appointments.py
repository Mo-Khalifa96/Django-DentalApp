import pytest
from .utils import render_error
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from datetime import time, timedelta
from patients.models import Patient, Appointment


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _appt_url(appt_id):
    return reverse('retrieve_update_cancel_appointment', kwargs={'id': appt_id})

def _create_payload(patient, doctor, procedure, appt_date=None, **overrides):
    if appt_date is None:
        appt_date = (timezone.localdate() + timedelta(days=3))
    base = {
        'patientId':   str(patient.id),
        'doctorId':    str(doctor.id),
        'procedureId': str(procedure.id),
        'type':        'routine_checkup',
        'date':        appt_date,
        'startTime':   '09:00:00',
        'endTime':     '10:00:00',
        'branchId':    None,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /appointments/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateAppointmentsAPIView:
    LIST_URL = 'list_create_appointments'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_appointments(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        proc = procedure_factory()
        a1 = appointment_factory(patient=patient_factory(), doctor=dentist_user, procedure=proc)
        a2 = appointment_factory(patient=patient_factory(), doctor=dentist_user, procedure=proc)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['success'] is True
        assert response.data['pagination']['total'] >= 2
        ids = [i['id'] for i in response.data['data']]
        assert str(a1.id) in ids
        assert str(a2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"

    def test_list_page_size_is_50(self, api_client, admin_user):
        """ListCreateAppointmentsAPIView.paginate_queryset sets page_size = 50."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.data['pagination']['limit'] == 50

    def test_dentist_only_sees_own_appointments(
        self, api_client, dentist_user, other_dentist_user,
        patient_factory, procedure_factory, appointment_factory
    ):
        proc    = procedure_factory()
        visible = appointment_factory(patient=patient_factory(doctor=dentist_user),
                                      doctor=dentist_user, procedure=proc)
        appointment_factory(patient=patient_factory(doctor=other_dentist_user),
                            doctor=other_dentist_user, procedure=proc)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert [i['id'] for i in response.data['data']] == [str(visible.id)]

    def test_receptionist_sees_branch_filtered_appointments(
        self, api_client, user_factory, dentist_user, patient_factory,
        procedure_factory, appointment_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        recept = user_factory(role='receptionist')
        recept.branches.set([b1])

        proc    = procedure_factory()
        a_own   = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                      procedure=proc, branch=b1)
        a_other = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                      procedure=proc, branch=b2)

        api_client.force_authenticate(user=recept)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(a_own.id) in ids
        assert str(a_other.id) not in ids

    def test_appointments_of_deleted_patients_excluded(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        """AppointmentsManager: filter(patient__is_deleted=False)."""
        ghost = patient_factory()
        proc  = procedure_factory()
        appt  = appointment_factory(patient=ghost, doctor=dentist_user, procedure=proc)
        ghost.is_deleted = True
        ghost.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        ids = [i['id'] for i in response.data['data']]
        assert str(appt.id) not in ids

    def test_unauthenticated_cannot_list_appointments(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_create_appointment_for_existing_patient(
        self, api_client, receptionist_user, dentist_user,
        patient_factory, procedure_factory
    ):
        patient = patient_factory()
        proc    = procedure_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, dentist_user, proc),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_auto_sets_status_to_pending(
        self, api_client, admin_user, dentist_user, patient_factory, procedure_factory
    ):
        """Appointment.save(): status defaults to 'pending'."""
        patient = patient_factory()
        proc    = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, dentist_user, proc),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        appt = Appointment.objects.get(id=response.data['data']['id'])
        assert appt.status == Appointment.AppointmentStatusChoices.PENDING

    def test_create_sets_snapshot_fields(
        self, api_client, admin_user, dentist_user, patient_factory, procedure_factory
    ):
        """Appointment.save(): procedureName and doctorName captured on creation."""
        proc    = procedure_factory(name='Root Canal')
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, dentist_user, proc),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        appt = Appointment.objects.get(id=response.data['data']['id'])
        assert appt.procedureName == 'Root Canal'
        assert appt.doctorName    == dentist_user.name

    def test_create_updates_patient_next_appointment(
        self, api_client, receptionist_user, dentist_user, patient_factory, procedure_factory
    ):
        """Appointment.save(): patient.nextAppointment updated to the new appointment date."""
        patient  = patient_factory(doctor=None)
        proc     = procedure_factory()
        appt_date = timezone.localdate() + timedelta(days=5)
        api_client.force_authenticate(user=receptionist_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, dentist_user, proc,
                            appt_date=appt_date.isoformat()),
            format='json',
        )
        patient.refresh_from_db()
        assert patient.nextAppointment == appt_date

    def test_create_assigns_doctor_to_existing_patient(
        self, api_client, receptionist_user, dentist_user, patient_factory, procedure_factory
    ):
        """CreateAppointmentSerializer.create(): existing patient.doctor = appointment.doctor."""
        patient = patient_factory(doctor=None)
        proc    = procedure_factory()
        api_client.force_authenticate(user=receptionist_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, dentist_user, proc),
            format='json',
        )
        patient.refresh_from_db()
        assert patient.doctor == dentist_user

    def test_create_new_patient_inline_creates_patient_and_dental_chart(
        self, api_client, receptionist_user, dentist_user, procedure_factory, branch
    ):
        """is_newPatient=True creates a Patient + DentalChart + Appointment atomically."""
        proc = procedure_factory()
        payload = {
            'is_newPatient': True,
            'newPatientDetails': {
                'name':        'Inline New Patient',
                'age':         25,
                'gender':      'Female',
                'countryCode': '20',
                'phone':       '01077776666',
            },
            'doctorId':    str(dentist_user.id),
            'procedureId': str(proc.id),
            'type':        'routine_checkup',
            'date':        (timezone.localdate() + timedelta(days=3)).isoformat(),
            'startTime':   '11:00:00',
            'endTime':     '12:00:00',
            'branchId':    str(branch.id),
        }
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        new_patient = Patient.objects.get(name='Inline New Patient')
        assert new_patient.doctor == dentist_user
        assert new_patient.patient_dentalchart is not None
        assert Appointment.objects.filter(id=response.data['data']['id'],
                                          patient=new_patient).exists()

    def test_create_rejects_conflicting_time_slot(
        self, api_client, receptionist_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory, branch
    ):
        """Appointment.validate_availability() raises AppointmentConflictError (409)."""
        proc     = procedure_factory()
        patient1 = patient_factory()
        patient2 = patient_factory()
        appt_date = timezone.localdate() + timedelta(days=2)

        appointment_factory(patient=patient1, doctor=dentist_user, procedure=proc,
                            date=appt_date, startTime=time(9, 0), endTime=time(10, 0),
                            branch=branch)

        #use receptionist's assigned branch under the hood
        receptionist_user.branches.add(branch)
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient2, dentist_user, proc,
                            appt_date=appt_date,
                            startTime='09:30:00', endTime='10:30:00',),
                            # branchId=str(branch.id)),
            format='json',
        )
        assert response.status_code == status.HTTP_409_CONFLICT or render_error(response)
        assert response.data['error']['code'] == 'APPOINTMENT_CONFLICT'
        assert response.data['error']['conflictWith']['patientName'] == patient1.name

    def test_conflict_check_on_branch_basis(
        self, api_client, receptionist_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory, branch_factory
    ):

        b1 = branch_factory()
        b2 = branch_factory()
        proc     = procedure_factory()
        patient1 = patient_factory()
        patient2 = patient_factory()
        appt_date = timezone.localdate() + timedelta(days=4)

        appointment_factory(patient=patient1, doctor=dentist_user, procedure=proc,
                            date=appt_date, startTime=time(9, 0), endTime=time(10, 0),
                            branch=b1)

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient2, dentist_user, proc,
                            appt_date=appt_date.isoformat(),
                            startTime='09:00:00', endTime='10:00:00',
                            branchId=str(b2.id)),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_allows_non_conflicting_time_same_doctor(
        self, api_client, receptionist_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        """Non-overlapping times for the same doctor on the same day → 201."""
        proc      = procedure_factory()
        patient1  = patient_factory()
        patient2  = patient_factory()
        appt_date = timezone.localdate() + timedelta(days=5)
        appointment_factory(patient=patient1, doctor=dentist_user, procedure=proc,
                            date=appt_date, startTime=time(9, 0), endTime=time(10, 0))

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient2, dentist_user, proc,
                            appt_date=appt_date.isoformat(),
                            startTime='10:00:00', endTime='11:00:00'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_response_is_wrapped(
        self, api_client, admin_user, dentist_user, patient_factory, procedure_factory
    ):
        patient = patient_factory()
        proc    = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, dentist_user, proc),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | PATCH | DELETE  /appointments/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateCancelAppointmentAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_appointment_with_patient_phone(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        """RetrieveAppointmentSerializer.get_patientPhone() normalizes the phone."""
        patient = patient_factory(phone='01012345678', countryCode='20')
        proc    = procedure_factory()
        appt    = appointment_factory(patient=patient, doctor=dentist_user, procedure=proc)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_appt_url(appt.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['patientPhone'] == '01012345678'
        assert response.data['data']['patientId'] == patient.id

    def test_retrieve_response_is_wrapped_with_metadata(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        """RetrieveAppointmentSerializer inherits UserPermissionsMixin."""
        appt = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                   procedure=procedure_factory())
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_appt_url(appt.id))

        assert response.data.get('success') is True
        assert 'metadata' in response.data

    # ── UPDATE (PATCH / PUT) ──────────────────────────────────────────────────

    def test_admin_can_update_appointment_status(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        appt = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                   procedure=procedure_factory())
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _appt_url(appt.id), {'status': 'confirmed'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        appt.refresh_from_db()
        assert appt.status == 'confirmed'

    def test_update_rejects_conflicting_reschedule(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        """UpdateAppointmentSerializer.validate() also calls validate_availability."""
        proc     = procedure_factory()
        patient1 = patient_factory()
        patient2 = patient_factory()
        appt_date = timezone.localdate() + timedelta(days=6)

        appointment_factory(patient=patient1, doctor=dentist_user, procedure=proc,
                            date=appt_date, startTime=time(9, 0), endTime=time(10, 0))
        appt_to_move = appointment_factory(patient=patient2, doctor=dentist_user, procedure=proc,
                                           date=appt_date + timedelta(days=1),
                                           startTime=time(9, 0), endTime=time(10, 0))

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _appt_url(appt_to_move.id),
            {'date': appt_date.isoformat(), 'startTime': '09:30:00', 'endTime': '10:30:00'},
            format='json',
        )
        assert response.status_code == status.HTTP_409_CONFLICT or render_error(response)

    def test_update_response_is_wrapped(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        appt = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                   procedure=procedure_factory())
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _appt_url(appt.id), {'notes': 'updated'}, format='json'
        )
        assert response.data.get('success') is True
        assert 'data' in response.data

    # ── CANCEL (DELETE) ───────────────────────────────────────────────────────

    def test_cancel_appointment_sets_status_and_reason(
        self, api_client, receptionist_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        """cancel (DELETE) returns 200 with a message, not 204."""
        appt = appointment_factory(patient=patient_factory(doctor=dentist_user),
                                   doctor=dentist_user, procedure=procedure_factory())
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.delete(
            _appt_url(appt.id),
            {'reason': 'Patient not available.'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['success'] is True

        appt.refresh_from_db()
        assert appt.status == 'cancelled'
        assert appt.notes  == 'Patient not available.'

    def test_cancel_without_reason_still_succeeds(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        appt = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                   procedure=procedure_factory())
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_appt_url(appt.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        appt.refresh_from_db()
        assert appt.status == 'cancelled'

    def test_cancel_appointment_clears_patient_next_appointment(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        patient   = patient_factory()
        proc      = procedure_factory()
        appt_date = timezone.localdate() + timedelta(days=7)
        appt      = appointment_factory(patient=patient, doctor=dentist_user,
                                        procedure=proc, date=appt_date)
        patient.refresh_from_db()
        assert patient.nextAppointment == appt_date   #set on creation

        api_client.force_authenticate(user=admin_user)
        api_client.delete(_appt_url(appt.id), {}, format='json')

        patient.refresh_from_db()
        assert patient.nextAppointment == None

    def test_unauthenticated_cannot_cancel_appointment(
        self, api_client, dentist_user, patient_factory, procedure_factory, appointment_factory
    ):
        appt = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                   procedure=procedure_factory())
        response = api_client.delete(_appt_url(appt.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /appointments/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveAppointmentOptionsAPIView:
    URL = 'appointments_options'

    def test_authenticated_user_gets_options_payload(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'patientChoices', 'doctorChoices',
                    'typeChoices', 'statusChoices', 'roomChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['statusChoices']}
        expected = {c.value for c in Appointment.AppointmentStatusChoices}
        assert returned == expected

    def test_doctor_choices_filtered_by_branch_id(
        self, api_client, admin_user, dentist_user, branch
    ):
        """get_doctorChoices: filters by branch_id (User.branch active FK)."""
        dentist_user.branch = branch
        dentist_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(branch.id)})

        doctor_ids = {str(c['doctorId']) for c in response.data['doctorChoices']}
        assert str(dentist_user.id) in doctor_ids

    def test_patient_choices_empty_when_branches_exist_and_no_branch_id(
        self, api_client, admin_user, patient_factory, branch_factory
    ):
        """get_patientChoices: no branchId + Branch.objects.exists() → []."""
        branch_factory()
        patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['patientChoices'] == []

    def test_room_choices_reflect_branch_rooms(
        self, api_client, admin_user, branch_factory
    ):
        b = branch_factory(rooms=['Chair A', 'Chair B'])
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b.id)})
        room_values = [c['value'] for c in response.data['roomChoices']]
        assert room_values == ['Chair A', 'Chair B']

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)
