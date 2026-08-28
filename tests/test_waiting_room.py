import uuid
import pytest
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from django.utils import timezone
from clinic.models import WaitingRoom


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def waiting_room_factory(appointment_factory, patient_factory, procedure_factory, dentist_user):
    """
    Creates WaitingRoom entries via the ORM.
    Pass appointment=, branch= etc. to override defaults.
    WaitingRoom.save() auto-sets status='waiting' and arrivedAt=now().
    """
    def _create(**overrides):
        if 'appointment' not in overrides:
            overrides['appointment'] = appointment_factory(
                patient=patient_factory(),
                doctor=dentist_user,
                procedure=procedure_factory(),
            )
        return WaitingRoom.objects.create(**overrides)

    return _create


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /waiting-room/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateWaitingRoomItemsAPIView:
    LIST_URL = 'list_create_waiting_room_items'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_waiting_room_items_when_no_branches_exist(
        self, api_client, admin_user, waiting_room_factory
    ):
        """
        With no Branch rows, filter_by_branch returns the full queryset,
        so even admin (who has no assigned branch) sees all items.
        """
        item = waiting_room_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert str(item.id) in [str(i['id']) for i in response.data['data']]

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, waiting_room_factory
    ):
        waiting_room_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data

    def test_receptionist_with_view_waiting_room_can_list(
        self, api_client, receptionist_user, waiting_room_factory
    ):
        """receptionist has view.waitingRoom by default."""
        item = waiting_room_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert str(item.id) in [str(i['id']) for i in response.data['data']]

    def test_list_filtered_by_user_branch(
        self, api_client, user_factory, waiting_room_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='receptionist')
        user.branches.set([b1])

        item_own   = waiting_room_factory(branch=b1)
        item_other = waiting_room_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(i['id']) for i in response.data['data']]
        assert str(item_own.id) in ids
        assert str(item_other.id) not in ids

    def test_items_with_soft_deleted_branch_are_excluded(
        self, api_client, admin_user, waiting_room_factory, branch_factory
    ):
        """WaitingRoomManager: Q(branch__is_deleted=False) hides stale items."""
        active = branch_factory()
        dying  = branch_factory()
        visible = waiting_room_factory(branch=active)
        hidden  = waiting_room_factory(branch=dying)

        dying.is_deleted = True
        dying.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [str(i['id']) for i in response.data['data']]
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    def test_dentist_without_view_waiting_room_permission_gets_403(
        self, api_client, dentist_user
    ):
        """Dentist role explicitly excludes 'view.waitingRoom' from default perms."""
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_add_patient_to_waiting_room(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'branchId': None},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert WaitingRoom.objects.filter(appointment=appointment).exists()

    def test_create_auto_sets_status_to_waiting(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        """WaitingRoom.save() always sets status='waiting' on creation."""
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'branchId': None},
            format='json',
        )
        item = WaitingRoom.objects.get(appointment=appointment)
        assert item.status == WaitingRoom.StatusChoices.WAITING

    def test_create_auto_sets_arrived_at(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        """WaitingRoom.save() sets arrivedAt = now() on creation."""
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'branchId': None},
            format='json',
        )
        item = WaitingRoom.objects.get(appointment=appointment)
        assert item.arrivedAt is not None

    def test_create_with_branch_assigns_it(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user, branch
    ):
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'branchId': str(branch.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert WaitingRoom.objects.get(appointment=appointment).branch == branch

    def test_create_without_appointment_or_patient_returns_400(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), {'branchId': None}, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_response_is_wrapped(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_without_permission_cannot_create(
        self, api_client, dentist_user, appointment_factory, patient_factory,
        procedure_factory
    ):
        """dentist lacks view.waitingRoom → blocked at permission level."""
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_create_walkin_with_patient_id_only_succeeds(
        self, api_client, admin_user, patient_factory
    ):
        """
        No appointmentId, no explicit isWalkIn flag — omission is NOT treated
        as isWalkIn=False (data.get('isWalkIn') defaults to None, not False),
        so this should succeed as an implicit walk-in.
        """
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'patientId': str(patient.id), 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        item = WaitingRoom.objects.get(patient=patient, appointment__isnull=True)
        assert item.isWalkIn is True

    def test_create_walkin_with_explicit_isWalkIn_true_succeeds(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'patientId': str(patient.id), 'isWalkIn': True, 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_with_explicit_isWalkIn_false_and_no_appointment_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """Explicit isWalkIn=False without an appointmentId must be rejected."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'patientId': str(patient.id), 'isWalkIn': False, 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'appointmentId' in response.data['error']['fields']

    def test_create_with_appointment_forces_isWalkIn_false(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        """isWalkIn is server-derived from appointment presence, not client-set."""
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'isWalkIn': True, 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        item = WaitingRoom.objects.get(appointment=appointment)
        assert item.isWalkIn is False

    def test_create_with_appointment_auto_assigns_patient(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        """`data['patient'] = appointment.patient` regardless of whether patientId was sent."""
        patient = patient_factory()
        appointment = appointment_factory(
            patient=patient, doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        item = WaitingRoom.objects.get(appointment=appointment)
        assert item.patient == patient

    def test_create_with_mismatched_patient_and_appointment_returns_400(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        appointment_patient = patient_factory()
        other_patient = patient_factory()
        appointment = appointment_factory(
            patient=appointment_patient, doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'appointmentId': str(appointment.id), 'patientId': str(other_patient.id), 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'patientId' in response.data['error']['fields']
        assert not WaitingRoom.objects.filter(appointment=appointment).exists()

    def test_create_with_invalid_doctor_id_does_not_mutate_appointment(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user
    ):
        """
        Regression test: an invalid doctorId must 400 WITHOUT having already
        written a doctor reassignment to the Appointment. Guards against the
        ordering issues.
        """
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        original_doctor_id = appointment.doctor_id
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {
                'appointmentId': str(appointment.id),
                'doctorId': str(uuid.uuid4()),  #nonexistent doctor
                'branchId': None,
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        appointment.refresh_from_db()
        assert appointment.doctor_id == original_doctor_id
        assert not WaitingRoom.objects.filter(appointment=appointment).exists()

    def test_create_with_mismatched_patient_does_not_mutate_appointment_doctor(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user, user_factory
    ):
        other_doctor = user_factory(role='dentist')
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        other_patient = patient_factory()
        original_doctor_id = appointment.doctor_id
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {
                'appointmentId': str(appointment.id),
                'patientId': str(other_patient.id),
                'doctorId': str(other_doctor.id),
                'branchId': None,
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        appointment.refresh_from_db()
        assert appointment.doctor_id == original_doctor_id

    def test_create_with_valid_doctor_id_reassigns_appointment_doctor(
        self, api_client, admin_user, appointment_factory, patient_factory,
        procedure_factory, dentist_user, user_factory
    ):
        """Happy path for the reassignment write, to complement the two guard tests above."""
        new_doctor = user_factory(role='dentist')
        appointment = appointment_factory(
            patient=patient_factory(), doctor=dentist_user, procedure=procedure_factory()
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {
                'appointmentId': str(appointment.id),
                'doctorId': str(new_doctor.id),
                'branchId': None,
            },
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        appointment.refresh_from_db()
        assert appointment.doctor_id == new_doctor.id
        assert appointment.doctorName == new_doctor.name

    def test_create_walkin_response_includes_patient_snapshot(
        self, api_client, admin_user, patient_factory
    ):
        """get_patientId/get_patientName must resolve from obj.patient when appointment is None."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            {'patientId': str(patient.id), 'branchId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        data = response.data['data']
        assert data['patientId'] == patient.id
        assert data['patientName'] == patient.name
        assert data['appointmentId'] is None


# ══════════════════════════════════════════════════════════════════════════════
# PATCH | DELETE  /waiting-room/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateDeleteWaitingRoomItemAPIView:

    def _url(self, item_id):
        return reverse('update_delete_waiting_room_item', kwargs={'id': item_id})

    def test_get_method_not_allowed(
        self, api_client, admin_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(item.id))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED or render_error(response)

    def test_receptionist_can_update_room(
        self, api_client, receptionist_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'room': 'Chair 3'
        }
        response = api_client.patch(
            self._url(item.id),
            payload,
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        item.refresh_from_db()
        assert item.room == 'Chair 3'

    def test_receptionist_can_update_status(
        self, api_client, receptionist_user, waiting_room_factory
    ):

        item = waiting_room_factory()
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'status': 'in_chair'
        }
        api_client.patch(
            self._url(item.id),
            payload,
            format='json',
        )
        item.refresh_from_db()
        assert item.status == WaitingRoom.StatusChoices.IN_CHAIR

    def test_update_response_is_wrapped(
        self, api_client, admin_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        api_client.force_authenticate(user=admin_user)
        payload = {
            'room': 'Suite 1'
        }
        response = api_client.patch(
            self._url(item.id),
            payload,
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_not_in_item_branch_cannot_update(
        self, api_client, user_factory, waiting_room_factory, branch_factory
    ):
        """SystemBasePermission.has_object_permission checks branch membership."""
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='receptionist')
        user.branches.set([b1])
        item = waiting_room_factory(branch=b2)

        api_client.force_authenticate(user=user)
        payload = {
            'room': 'Chair 2'
        }
        response = api_client.patch(
            self._url(item.id),
            payload,
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_user_without_permission_cannot_update(
        self, api_client, dentist_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        api_client.force_authenticate(user=dentist_user)
        payload = {
            'room': 'Chair 3'
        }
        response = api_client.patch(
            self._url(item.id),
            payload,
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_status_transition_to_in_chair_sets_started_at(
        self, api_client, receptionist_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        assert item.startedAt is None
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            self._url(item.id), {'status': 'in_chair'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        item.refresh_from_db()
        assert item.startedAt is not None


    def test_status_transition_to_done_sets_completed_at_and_completes_appointment(
        self, api_client, receptionist_user, waiting_room_factory, appointment_factory,
        patient_factory, dentist_user, procedure_factory
    ):
        """
        WaitingRoom.save(): status='done' also marks the linked appointment
        'completed', sets its endTime, and clears the patient's nextAppointment.
        """
        patient = patient_factory(nextAppointment=timezone.localdate())
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure_factory())
        item = waiting_room_factory(appointment=appointment)

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            self._url(item.id), {'status': 'done'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)

        item.refresh_from_db()
        assert item.completedAt is not None

        appointment.refresh_from_db()
        assert appointment.status == 'completed'
        assert appointment.endTime is not None

        patient.refresh_from_db()
        assert patient.nextAppointment is None


    def test_status_done_for_walkin_item_does_not_touch_appointment(
        self, api_client, receptionist_user, waiting_room_factory, patient_factory
    ):
        """WaitingRoom.save(): the appointment-completion cascade only runs
        `if self.appointment` — a walk-in item (no appointment) safely skips it."""
        patient = patient_factory()
        item = waiting_room_factory(appointment=None, patient=patient)

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            self._url(item.id), {'status': 'done'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        item.refresh_from_db()
        assert item.completedAt is not None

    def test_re_saving_in_chair_item_does_not_overwrites_startedAt_time(
        self, api_client, receptionist_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        api_client.force_authenticate(user=receptionist_user)

        api_client.patch(self._url(item.id), {'status': 'in_chair'}, format='json')
        item.refresh_from_db()
        original_started_at = item.startedAt
        assert original_started_at is not None

        response = api_client.patch(self._url(item.id), {'room': 'Chair 5'}, format='json')
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        item.refresh_from_db()
        assert item.startedAt == original_started_at


    def test_re_saving_done_item_does_not_overwrite_completedAt_time(
        self, api_client, receptionist_user, waiting_room_factory, appointment_factory,
        patient_factory, dentist_user, procedure_factory
    ):
        patient = patient_factory()
        appointment = appointment_factory(patient=patient, doctor=dentist_user, procedure=procedure_factory())
        item = waiting_room_factory(appointment=appointment)

        api_client.force_authenticate(user=receptionist_user)
        api_client.patch(self._url(item.id), {'status': 'done'}, format='json')
        item.refresh_from_db()
        original_completed_at = item.completedAt
        assert original_completed_at is not None

        response = api_client.patch(self._url(item.id), {'room': 'Chair 5'}, format='json')
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        item.refresh_from_db()
        assert item.completedAt == original_completed_at

    def test_admin_can_delete_waiting_room_item(
        self, api_client, admin_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        iid = item.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(iid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not WaitingRoom.objects.filter(id=iid).exists()
        assert not WaitingRoom.all_objects.filter(id=iid).exists()

    def test_user_without_permission_cannot_delete(
        self, api_client, dentist_user, waiting_room_factory
    ):
        item = waiting_room_factory()
        api_client.force_authenticate(user=dentist_user)
        response = api_client.delete(self._url(item.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_delete(self, api_client, waiting_room_factory):
        item = waiting_room_factory()
        response = api_client.delete(self._url(item.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_delete_nonexistent_item_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /waiting-room/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveWaitingRoomOptionsAPIView:
    """BranchToSerializerMixin + plain generics.GenericAPIView; no ResponseMixin."""
    URL = 'waiting_room_options'

    def test_authenticated_user_gets_options(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'doctorChoices', 'statusChoices', 'roomChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'success' not in response.data

    def test_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['statusChoices']}
        expected = {c.value for c in WaitingRoom.StatusChoices}
        assert returned == expected

    def test_doctor_choices_empty_when_no_branch_id_and_branches_exist(
        self, api_client, admin_user, branch_factory
    ):
        """get_doctorChoices: no branchId + Branch.objects.exists() → []."""
        branch_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['doctorChoices'] == []

    def test_doctor_choices_filtered_by_branch_id(
        self, api_client, admin_user, dentist_user, branch_factory
    ):
        """
        get_doctorChoices filters by User.branch_id (active branch FK)
        and role in ['dentist', 'admin'].
        """
        b = branch_factory()
        dentist_user.branch = b
        dentist_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b.id)})
        doctor_ids = {str(c['doctorId']) for c in response.data['doctorChoices']}
        assert str(dentist_user.id) in doctor_ids

    def test_room_choices_empty_when_no_branch_id(self, api_client, admin_user):
        """get_roomChoices: no branchId → []."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['roomChoices'] == []

    def test_room_choices_reflect_branch_rooms(
        self, api_client, admin_user, branch_factory
    ):
        """get_roomChoices returns the branch.rooms list for the given branchId."""
        b = branch_factory(rooms=['Op 1', 'Op 2', 'Op 3'])
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b.id)})
        room_values = [c['value'] for c in response.data['roomChoices']]
        assert room_values == ['Op 1', 'Op 2', 'Op 3']

    def test_invalid_branch_id_returns_400(self, api_client, admin_user):
        """BranchToSerializerMixin raises ValidationError for nonexistent branchId."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)