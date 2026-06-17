import uuid
import pytest
from django.urls import reverse
from rest_framework import status
from clinic.models import Branch, WorkingDaysLookUp


#Helper function
def _branch_payload(**overrides):
    """Return a minimal valid branch creation payload, with optional overrides."""
    base = {
        'name': 'New Branch',
        'phone': '+20101234567',
        'workingDays': [0, 1, 2, 3, 4],   # Sun – Thu
        'openTime': '09:00:00',
        'closeTime': '17:00:00',
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /branches/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateBranchesAPIView:
    URL = 'list_create_branches'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_branches(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(b['id']) for b in response.data['data']]
        assert str(branch.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing top-level key: {key}"

    def test_list_pagination_object_has_required_fields(
        self, api_client, admin_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        pagination = response.data['pagination']
        for key in ('page', 'limit', 'total', 'totalPages', 'hasNext', 'hasPrev'):
            assert key in pagination, f"Missing pagination key: {key}"

    def test_list_metadata_contains_user_permissions(
        self, api_client, admin_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'userPermissions' in response.data['metadata']

    def test_list_excludes_soft_deleted_branches(
        self, api_client, admin_user, branch_factory
    ):
        visible = branch_factory(name='Visible Branch')
        hidden = branch_factory(name='Deleted Branch')
        hidden.is_deleted = True
        hidden.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [str(b['id']) for b in response.data['data']]
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    def test_list_fields_exclude_rooms_and_is_main(
        self, api_client, admin_user, branch
    ):
        """BranchSerializer used for lists must not expose rooms or isMain."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        item = next(b for b in response.data['data'] if str(b['id']) == str(branch.id))
        assert 'rooms' not in item
        assert 'isMain' not in item

    def test_list_can_be_searched_by_name(
        self, api_client, admin_user, branch_factory
    ):
        alpha = branch_factory(name='Alpha Clinic')
        branch_factory(name='Beta Clinic')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'search': 'Alpha'})

        assert response.status_code == status.HTTP_200_OK
        ids = [str(b['id']) for b in response.data['data']]
        assert str(alpha.id) in ids

    def test_non_admin_cannot_list_branches(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_list_branches(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_branch(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), _branch_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Branch.objects.filter(name='New Branch').exists()

    def test_create_response_is_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), _branch_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_create_response_data_includes_rooms_and_is_main(
        self, api_client, admin_user
    ):
        """CreateBranchSerializer exposes rooms and isMain; list serializer does not."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), _branch_payload(), format='json'
        )

        data = response.data['data']
        assert 'rooms' in data
        assert 'isMain' in data

    def test_first_branch_auto_assigned_as_main(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        api_client.post(reverse(self.URL), _branch_payload(), format='json')

        created = Branch.objects.get(name='New Branch')
        assert created.isMain is True

    def test_subsequent_branch_not_auto_main(
        self, api_client, admin_user, branch
    ):
        """When at least one branch already exists, new branches are not set as main."""
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.URL),
            _branch_payload(name='Second Branch'),
            format='json',
        )

        second = Branch.objects.get(name='Second Branch')
        assert second.isMain is False

    def test_explicit_is_main_true_is_honored(
        self, api_client, admin_user, branch
    ):
        """Client can explicitly flag a new branch as main."""
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.URL),
            _branch_payload(name='Explicit Main', isMain=True),
            format='json',
        )

        created = Branch.objects.get(name='Explicit Main')
        assert created.isMain is True

    def test_default_room_assigned_when_rooms_omitted(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        api_client.post(reverse(self.URL), _branch_payload(), format='json')

        created = Branch.objects.get(name='New Branch')
        assert created.rooms == ['Chair 1']

    def test_custom_rooms_are_persisted(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        payload = _branch_payload(rooms=['Room A', 'Room B', 'Room C'])
        api_client.post(reverse(self.URL), payload, format='json')

        created = Branch.objects.get(name='New Branch')
        assert created.rooms == ['Room A', 'Room B', 'Room C']

    def test_working_days_duplicates_are_removed_on_create(
        self, api_client, admin_user
    ):
        """Serializer validate_workingDays deduplicates and sorts before saving."""
        api_client.force_authenticate(user=admin_user)
        payload = _branch_payload(workingDays=[1, 1, 3, 3, 5])
        api_client.post(reverse(self.URL), payload, format='json')

        created = Branch.objects.get(name='New Branch')
        assert created.workingDays == sorted({1, 3, 5})

    def test_create_with_empty_working_days_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), _branch_payload(workingDays=[]), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_invalid_working_day_value_returns_400(
        self, api_client, admin_user
    ):
        """Values outside 0-6 must be rejected by TranslatedChoiceField."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), _branch_payload(workingDays=[0, 7, 99]), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_invalid_phone_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), _branch_payload(phone='not-a-phone'), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_missing_required_fields_returns_400(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.URL), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_admin_cannot_create_branch(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.URL), _branch_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_create_branch(self, api_client):
        response = api_client.post(
            reverse(self.URL), _branch_payload(), format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# GET | PATCH | PUT | DELETE  /branches/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteBranchAPIView:

    def _url(self, branch_id):
        return reverse('retrieve_update_delete_branch', kwargs={'id': branch_id})

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_branch(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(branch.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['name'] == branch.name

    def test_retrieve_response_is_wrapped(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(branch.id))

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_retrieve_response_includes_user_permissions_in_metadata(
        self, api_client, admin_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(branch.id))

        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_retrieve_data_contains_expected_fields(
        self, api_client, admin_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(branch.id))

        data = response.data['data']
        for field in ('id', 'name', 'phone', 'workingDays', 'openTime', 'closeTime', 'createdAt'):
            assert field in data, f"Missing field in detail response: {field}"

    def test_non_admin_cannot_retrieve_branch(
        self, api_client, dentist_user, branch
    ):
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(self._url(branch.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_retrieve_branch(self, api_client, branch):
        response = api_client.get(self._url(branch.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_nonexistent_branch_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ── UPDATE (PATCH) ────────────────────────────────────────────────────────

    def test_admin_can_partial_update_name(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(branch.id), {'name': 'Renamed Branch'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        branch.refresh_from_db()
        assert branch.name == 'Renamed Branch'

    def test_admin_can_update_working_days(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        new_days = [1, 2, 3, 4, 5]   # Mon – Fri
        response = api_client.patch(
            self._url(branch.id), {'workingDays': new_days}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        branch.refresh_from_db()
        assert branch.workingDays == new_days

    def test_update_working_days_deduplicates(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            self._url(branch.id), {'workingDays': [2, 2, 4, 4, 6]}, format='json'
        )

        branch.refresh_from_db()
        assert branch.workingDays == sorted({2, 4, 6})

    def test_update_with_empty_working_days_returns_400(
        self, api_client, admin_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(branch.id), {'workingDays': []}, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_admin_can_update_rooms(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        new_rooms = ['Suite A', 'Suite B', 'Suite C']
        response = api_client.patch(
            self._url(branch.id), {'rooms': new_rooms}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        branch.refresh_from_db()
        assert branch.rooms == new_rooms

    def test_admin_can_set_branch_as_main(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(branch.id), {'isMain': True}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        branch.refresh_from_db()
        assert branch.isMain is True

    def test_admin_can_update_address(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(branch.id),
            {'address': '123 Nile Street, Cairo'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        branch.refresh_from_db()
        assert branch.address == '123 Nile Street, Cairo'

    def test_update_response_is_wrapped(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(branch.id), {'name': 'Updated'}, format='json'
        )

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_non_admin_cannot_patch_branch(
        self, api_client, receptionist_user, branch
    ):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            self._url(branch.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_patch_branch(self, api_client, branch):
        response = api_client.patch(
            self._url(branch.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── UPDATE (PUT) ──────────────────────────────────────────────────────────

    def test_admin_can_full_update_branch(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        payload = {
            'name': 'Fully Updated Branch',
            'phone': '+20109876543',
            'workingDays': [0, 1, 2, 3, 4, 5],
            'openTime': '08:00:00',
            'closeTime': '20:00:00',
            'rooms': ['Op 1', 'Op 2'],
        }
        response = api_client.put(self._url(branch.id), payload, format='json')

        assert response.status_code == status.HTTP_200_OK
        branch.refresh_from_db()
        assert branch.name == 'Fully Updated Branch'
        assert branch.openTime.strftime('%H:%M:%S') == '08:00:00'
        assert branch.rooms == ['Op 1', 'Op 2']

    def test_non_admin_cannot_put_branch(
        self, api_client, assistant_user, branch
    ):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.put(
            self._url(branch.id), _branch_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_hard_deletes_branch(self, api_client, admin_user, branch):
        """
        BranchManager.delete_branch hard-deletes when user.role == 'admin'.
        The record must be absent even from all_objects after deletion.
        """
        bid = branch.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(bid))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Branch.objects.filter(id=bid).exists()
        assert not Branch.all_objects.filter(id=bid).exists()

    def test_non_admin_cannot_delete_branch(
        self, api_client, receptionist_user, branch
    ):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.delete(self._url(branch.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_delete_branch(self, api_client, branch):
        response = api_client.delete(self._url(branch.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_nonexistent_branch_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════════════
# GET  /branches/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveBranchOptionsAPIView:
    """
    RetrieveBranchOptionsAPIView inherits from plain rest_framework.generics.GenericAPIView
    (not the project's base view), so ResponseMixin is NOT applied.
    The response is a bare dict: {'weekDaysChoices': [...]}.
    """
    URL = 'branches_options'

    def test_authenticated_user_gets_options(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        assert 'weekDaysChoices' in response.data

    def test_non_admin_can_access_options(self, api_client, dentist_user):
        """Options requires IsAuthenticated only, not AdminOnly."""
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK

    def test_week_days_choices_cover_all_seven_days(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert len(response.data['weekDaysChoices']) == len(WorkingDaysLookUp)

    def test_week_days_choices_have_value_and_label_keys(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        for choice in response.data['weekDaysChoices']:
            assert 'value' in choice, "Each day choice must have a 'value' key"
            assert 'label' in choice, "Each day choice must have a 'label' key"

    def test_week_days_values_match_working_days_lookup(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['weekDaysChoices']}
        expected = set(WorkingDaysLookUp.values)   # {0, 1, 2, 3, 4, 5, 6}
        assert returned == expected

    def test_response_is_not_wrapped_by_response_mixin(
        self, api_client, admin_user
    ):
        """
        Unlike list/detail views, the options view uses the bare DRF GenericAPIView.
        The ResponseMixin wrapping {'success', 'data'} must NOT be present.
        """
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert 'success' not in response.data
        assert 'data' not in response.data

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED