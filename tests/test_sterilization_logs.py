import uuid
import pytest
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from clinic.models import SterilizationLog


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def log_factory():
    def _create(**overrides):
        defaults = {
            'cycleType':      'gravity',
            'instrumentSets': ['basic_exam_kit']
        }
        defaults.update(overrides)
        return SterilizationLog.objects.create(**defaults)

    return _create


# ─────────────────────────────────────────────────────────────────────────────
# Payload helper
# ─────────────────────────────────────────────────────────────────────────────

def _create_payload(**overrides):
    """Minimal valid create payload (date/time are read-only; auto-set by save)."""
    base = {
        'cycleType':      'gravity',
        'instrumentSets': ['basic_exam_kit'],
        'result': '',
        'branchId': None,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /sterilization/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateSterilizationLogsAPIView:
    LIST_URL = 'list_create_sterilization_logs'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_logs(self, api_client, admin_user, log_factory):
        log1 = log_factory()
        log2 = log_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(l['id']) for l in response.data['data']]
        assert str(log1.id) in ids
        assert str(log2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, log_factory
    ):
        log_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"

    def test_user_with_view_permission_can_list(
        self, api_client, assistant_user, log_factory
    ):
        """assistant has view.sterilizationLogs; no branches → sees all logs."""
        log = log_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert str(log.id) in [str(l['id']) for l in response.data['data']]

    def test_list_filtered_by_user_branch(
        self, api_client, user_factory, log_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='assistant')
        user.branches.set([b1])

        log_own   = log_factory(branch=b1)
        log_other = log_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(l['id']) for l in response.data['data']]
        assert str(log_own.id) in ids
        assert str(log_other.id) not in ids

    def test_logs_with_soft_deleted_branch_are_excluded(
        self, api_client, admin_user, log_factory, branch_factory
    ):
        active = branch_factory()
        dying  = branch_factory()
        visible = log_factory(branch=active)
        hidden  = log_factory(branch=dying)

        dying.is_deleted = True
        dying.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [str(l['id']) for l in response.data['data']]
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    def test_log_with_null_branch_is_always_visible(
        self, api_client, admin_user, log_factory
    ):
        log = log_factory(branch=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(log.id) in [str(l['id']) for l in response.data['data']]

    def test_receptionist_without_permission_gets_403(
        self, api_client, receptionist_user
    ):
        """receptionist lacks view.sterilizationLogs by default."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_sterilization_log(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_auto_sets_operator_from_user_name(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(operator=None), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        log = SterilizationLog.objects.latest('createdAt')
        assert log.operator == admin_user.name

    def test_create_with_explicit_operator_uses_it(self, api_client, admin_user):
        """validate_operator falls through when operator is provided."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(operator='Tech A'),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        log = SterilizationLog.objects.latest('createdAt')
        assert log.operator == 'Tech A'

    def test_create_with_result_passed_auto_sets_sealed_at(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(result='passed'),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        log = SterilizationLog.objects.latest('createdAt')
        assert log.sealedAt is not None

    def test_create_with_empty_instrument_sets_returns_400(self, api_client, admin_user):
        """validate_instrumentSets: empty list → ValidationError."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(instrumentSets=[]),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_invalid_instrument_set_returns_400(self, api_client, admin_user):
        """validate_instrumentSets: unknown choice → ValidationError."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(instrumentSets=['not_a_real_kit']),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_deduplicates_instrument_sets(self, api_client, admin_user):
        """validate_instrumentSets: duplicates removed and sorted."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(instrumentSets=['rct_kit', 'basic_exam_kit', 'rct_kit']),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        log = SterilizationLog.objects.latest('createdAt')
        assert log.instrumentSets == sorted({'rct_kit', 'basic_exam_kit'})

    def test_create_without_branch_id_returns_400(self, api_client, admin_user):
        """branchId is now required=True; omitting it entirely → 400."""
        api_client.force_authenticate(user=admin_user)
        payload = {'cycleType': 'gravity', 'instrumentSets': ['basic_exam_kit']}
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_explicit_branch(self, api_client, admin_user, branch):
        """Providing a valid branchId assigns the branch to the log."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(branchId=str(branch.id)),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        log = SterilizationLog.objects.latest('createdAt')
        assert log.branch == branch

    def test_create_response_is_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_with_create_permission_can_create(self, api_client, assistant_user):
        """assistant has create.sterilizationLog by default."""
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code != status.HTTP_403_FORBIDDEN or render_error(response)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_user_without_create_permission_cannot_create(
        self, api_client, receptionist_user
    ):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_create(self, api_client):
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# PATCH | DELETE  /sterilization/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateDeleteSterilizationLogAPIView:

    def _url(self, log_id):
        return reverse('update_delete_sterilization_log', kwargs={'id': log_id})

    def test_get_method_not_allowed(self, api_client, admin_user, log_factory):
        log = log_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(log.id))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED or render_error(response)

    def test_admin_can_update_result(self, api_client, admin_user, log_factory):
        log = log_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(log.id), {'result': 'passed'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        log.refresh_from_db()
        assert log.result == SterilizationLog.SterilizationResultChoices.PASSED

    def test_admin_can_update_notes(self, api_client, admin_user, log_factory):
        log = log_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(log.id), {'notes': 'Checked by supervisor'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        log.refresh_from_db()
        assert log.notes == 'Checked by supervisor'

    def test_read_only_fields_ignored_on_update(self, api_client, admin_user, log_factory):
        """date, time, branchId are read_only in UpdateSterilizationLogSerializer."""
        log = log_factory()
        original_date = str(log.date)
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            self._url(log.id),
            {'date': '2000-01-01', 'time': '00:00:00'},
            format='json',
        )

        log.refresh_from_db()
        assert str(log.date) == original_date

    def test_update_response_is_wrapped(self, api_client, admin_user, log_factory):
        log = log_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(log.id), {'result': 'failed'}, format='json'
        )
        
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_with_update_permission_can_update(
        self, api_client, assistant_user, log_factory
    ):
        """assistant has update.sterilizationLog by default."""
        log = log_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.patch(
            self._url(log.id), {'result': 'passed'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_user_not_in_log_branch_cannot_update(
        self, api_client, user_factory, log_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='assistant')
        user.branches.set([b1])
        log = log_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.patch(
            self._url(log.id), {'result': 'passed'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_user_without_update_permission_cannot_update(
        self, api_client, receptionist_user, log_factory
    ):
        log = log_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            self._url(log.id), {'result': 'passed'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_admin_can_delete_log(self, api_client, admin_user, log_factory):
        log = log_factory()
        lid = log.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(lid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not SterilizationLog.objects.filter(id=lid).exists()
        assert not SterilizationLog.all_objects.filter(id=lid).exists()

    def test_user_without_delete_permission_cannot_delete(
        self, api_client, assistant_user, log_factory
    ):
        """assistant has update but not delete permission."""
        log = log_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.delete(self._url(log.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_delete_nonexistent_log_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /sterilization/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveSterilizationLogsOptionsAPIView:
    """Plain generics.GenericAPIView — ResponseMixin is NOT applied."""
    URL = 'sterilization_logs_options'

    def test_authenticated_user_gets_options(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'cycleTypeChoices', 'instrumentSetsChoices', 'resultChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'success' not in response.data

    def test_cycle_type_choices_cover_all_types(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['cycleTypeChoices']}
        expected = {c.value for c in SterilizationLog.CycleTypeChoices}
        assert returned == expected

    def test_instrument_set_choices_cover_all_sets(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['instrumentSetsChoices']}
        expected = {c.value for c in SterilizationLog.InstrumentSetsChoices}
        assert returned == expected

    def test_result_choices_cover_passed_and_failed(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['resultChoices']}
        assert returned == {'passed', 'failed'}

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)