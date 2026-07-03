import uuid
import pytest
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from datetime import date, timedelta
from patients.models import PatientRecall


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def recall_factory(patient_factory):
    """
    Creates PatientRecall instances via the ORM.
    save() auto-sets status='pending' and phone from patient.phone.
    Override any field with keyword args.
    """
    def _create(**overrides):
        defaults = {
            'patient': patient_factory(),
            'type':    'checkup',
            'dueDate': date.today() + timedelta(days=30),
        }
        defaults.update(overrides)
        return PatientRecall.objects.create(**defaults)

    return _create


# ─────────────────────────────────────────────────────────────────────────────
# Payload helper
# ─────────────────────────────────────────────────────────────────────────────

def _create_payload(patient, **overrides):
    base = {
        'patientId': str(patient.id),
        'type':      'checkup',
        'dueDate':   str(date.today() + timedelta(days=30)),
        'branchId':  None,
    }
    base.update(overrides)
    return base

def _recall_url(recall_id):
    return reverse('update_delete_patient_recall', kwargs={'id': recall_id})


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /recalls/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreatePatientRecallsAPIView:
    LIST_URL = 'list_create_patient_recalls'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_recalls(
        self, api_client, admin_user, recall_factory
    ):
        r1 = recall_factory()
        r2 = recall_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(r['id']) for r in response.data['data']]
        assert str(r1.id) in ids
        assert str(r2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, recall_factory
    ):
        recall_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"

    def test_list_page_size_is_50(self, api_client, admin_user, recall_factory):
        """paginate_queryset sets page_size = 50."""
        recall_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.data['pagination']['limit'] == 50

    def test_dentist_sees_only_own_patients_recalls(
        self, api_client, dentist_user, other_dentist_user, patient_factory, recall_factory
    ):
        """get_queryset: dentist path → filter(patient__doctor=user)."""
        patient_own   = patient_factory(doctor=dentist_user)
        patient_other = patient_factory(doctor=other_dentist_user)
        recall_own   = recall_factory(patient=patient_own)
        recall_other = recall_factory(patient=patient_other)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(r['id']) for r in response.data['data']]
        assert str(recall_own.id) in ids
        assert str(recall_other.id) not in ids

    def test_receptionist_sees_branch_filtered_recalls(
        self, api_client, user_factory, recall_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='receptionist')
        user.branches.set([b1])

        recall_own   = recall_factory(branch=b1)
        recall_other = recall_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(r['id']) for r in response.data['data']]
        assert str(recall_own.id) in ids
        assert str(recall_other.id) not in ids

    def test_recalls_of_deleted_patients_are_excluded(
        self, api_client, admin_user, patient_factory, recall_factory
    ):
        """PatientRecallsManager: filter(patient__is_deleted=False)."""
        ghost = patient_factory()
        recall = recall_factory(patient=ghost)

        ghost.is_deleted = True
        ghost.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(recall.id) not in [str(r['id']) for r in response.data['data']]

    def test_assistant_without_recall_permission_gets_403(
        self, api_client, assistant_user
    ):
        """assistant default permissions do not include view.recalls."""
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_recall(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert PatientRecall.objects.filter(patient=patient).exists()

    def test_create_auto_sets_status_to_pending(
        self, api_client, admin_user, patient_factory
    ):
        """status is read_only in CreatePatientRecallSerializer; save() defaults to 'pending'."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        recall = PatientRecall.objects.get(patient=patient)
        assert recall.status == PatientRecall.RecallStatusChoices.PENDING

    def test_create_auto_sets_phone_from_patient_when_omitted(
        self, api_client, admin_user, patient_factory
    ):
        """save(): if phone not provided → phone = patient.phone."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        recall = PatientRecall.objects.get(patient=patient)
        assert recall.phone == patient.phone

    def test_create_with_custom_phone_uses_it(
        self, api_client, admin_user, patient_factory
    ):
        """save(): if phone is provided → save() skips auto-assign."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, phone='+20199999999'),
            format='json',
        )
        recall = PatientRecall.objects.get(patient=patient)
        assert recall.phone == '+20199999999'

    def test_create_without_branch_id_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """branchId is now required=True; omitting it entirely → 400."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        payload = {
            'patientId': str(patient.id),
            'type': 'checkup',
            'dueDate': str(date.today() + timedelta(days=30)),
            #o branchId key
        }
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_auto_assigns_branch_from_user_active_branch(
        self, api_client, admin_user, patient_factory, branch
    ):
        """ValidateBranchMixin: branchId=null + user.branch set → auto-assign."""
        admin_user.branch = branch
        admin_user.branches.add(branch)
        admin_user.save(update_fields=['branch', 'updatedAt'])

        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        recall = PatientRecall.objects.get(patient=patient)
        assert recall.branch == branch

    def test_create_response_is_wrapped(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_with_create_recall_permission_can_create(
        self, api_client, receptionist_user, patient_factory
    ):
        """receptionist has create.recall by default."""
        patient = patient_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_assistant_cannot_create_recall(
        self, api_client, assistant_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_create(self, api_client, patient_factory):
        patient = patient_factory()
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient), format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# PATCH | DELETE  /recalls/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateDeletePatientRecallAPIView:

    def test_get_method_not_allowed(self, api_client, admin_user, recall_factory):
        """GET excluded from http_method_names → 405."""
        recall = recall_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_recall_url(recall.id))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED or render_error(response)

    def test_admin_can_update_status(self, api_client, admin_user, recall_factory):
        recall = recall_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _recall_url(recall.id), {'status': 'confirmed'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        recall.refresh_from_db()
        assert recall.status == PatientRecall.RecallStatusChoices.CONFIRMED

    def test_status_contacted_triggers_contacted_at(
        self, api_client, admin_user, recall_factory
    ):
        """save(): status == 'contacted' and not contactedAt → contactedAt set to now()."""
        recall = recall_factory()
        assert recall.contactedAt is None

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _recall_url(recall.id), {'status': 'contacted'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        recall.refresh_from_db()
        assert recall.contactedAt is not None

    def test_admin_can_update_due_date_and_notes(
        self, api_client, admin_user, recall_factory
    ):
        recall = recall_factory()
        new_due = str(date.today() + timedelta(days=60))
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _recall_url(recall.id),
            {'dueDate': new_due, 'notes': 'Follow up required'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        recall.refresh_from_db()
        assert str(recall.dueDate) == new_due
        assert recall.notes == 'Follow up required'

    def test_phone_is_read_only_on_update(self, api_client, admin_user, recall_factory):
        """UpdatePatientRecallSerializer marks phone as read_only."""
        recall = recall_factory()
        original_phone = recall.phone
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _recall_url(recall.id), {'phone': '+20100000000'}, format='json'
        )
        recall.refresh_from_db()
        assert recall.phone == original_phone

    def test_branch_id_is_read_only_on_update(
        self, api_client, admin_user, recall_factory, branch_factory
    ):
        """branchId is in read_only_fields in UpdatePatientRecallSerializer."""
        b_original = branch_factory()
        b_new = branch_factory()
        recall = recall_factory(branch=b_original)
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _recall_url(recall.id), {'branchId': str(b_new.id)}, format='json'
        )
        recall.refresh_from_db()
        assert recall.branch == b_original

    def test_update_response_is_wrapped(self, api_client, admin_user, recall_factory):
        recall = recall_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _recall_url(recall.id), {'status': 'no_answer'}, format='json'
        )
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_with_update_permission_can_update(
        self, api_client, receptionist_user, recall_factory
    ):
        """receptionist has update.recall by default."""
        recall = recall_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            _recall_url(recall.id), {'status': 'no_answer'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_user_not_in_recall_branch_cannot_update(
        self, api_client, user_factory, recall_factory, branch_factory
    ):
        """SystemBasePermission.has_object_permission checks recall.branch_id."""
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='receptionist')
        user.branches.set([b1])
        recall = recall_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.patch(
            _recall_url(recall.id), {'status': 'confirmed'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_admin_can_delete_recall(self, api_client, admin_user, recall_factory):
        recall = recall_factory()
        rid = recall.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_recall_url(rid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not PatientRecall.objects.filter(id=rid).exists()
        assert not PatientRecall.all_objects.filter(id=rid).exists()

    def test_user_without_delete_permission_cannot_delete(
        self, api_client, assistant_user, recall_factory
    ):
        recall = recall_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.delete(_recall_url(recall.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_delete(self, api_client, recall_factory):
        recall = recall_factory()
        response = api_client.delete(_recall_url(recall.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_delete_nonexistent_recall_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_recall_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /recalls/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrievePatientRecallsOptionsAPIView:
    """
    Plain generics.GenericAPIView + BranchToSerializerMixin.
    ResponseMixin NOT applied.
    """
    URL = 'patient_recalls_options'

    def test_authenticated_user_gets_options_payload(
        self, api_client, receptionist_user
    ):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'patientChoices', 'recallTypeChoices', 'recallStatusChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'success' not in response.data

    def test_recall_type_choices_cover_all_types(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['recallTypeChoices']}
        expected = {c.value for c in PatientRecall.RecallTypeChoices}
        assert returned == expected

    def test_recall_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['recallStatusChoices']}
        expected = {c.value for c in PatientRecall.RecallStatusChoices}
        assert returned == expected

    def test_patient_choices_return_all_patients_when_no_filters(
        self, api_client, admin_user, patient_factory
    ):
        """
        The branch-guard is COMMENTED OUT in get_patientChoices; patients are
        always returned without branchId/doctorId, unlike lab orders options.
        """
        p1 = patient_factory()
        p2 = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        patient_ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p1.id) in patient_ids
        assert str(p2.id) in patient_ids

    def test_patient_choices_filtered_by_branch_id(
        self, api_client, admin_user, patient_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        p_b1 = patient_factory(branch=b1)
        p_b2 = patient_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        patient_ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p_b1.id) in patient_ids
        assert str(p_b2.id) not in patient_ids

    def test_patient_choices_filtered_by_doctor_id(
        self, api_client, admin_user, patient_factory, dentist_user
    ):
        """doctorId QP filters patients by doctor FK."""
        p_own   = patient_factory(doctor=dentist_user)
        p_other = patient_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'doctorId': str(dentist_user.id)})

        patient_ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p_own.id) in patient_ids
        assert str(p_other.id) not in patient_ids

    def test_invalid_doctor_id_returns_400(self, api_client, admin_user):
        """Provided doctorId must belong to a dentist or admin user."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'doctorId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_receptionist_as_doctor_id_returns_400(
        self, api_client, admin_user, receptionist_user
    ):
        """doctorId must be role in ['dentist', 'admin']; receptionist → 400."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(
            reverse(self.URL), {'doctorId': str(receptionist_user.id)}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)
