import uuid
import pytest
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from clinic.models import Procedure


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detail_url(procedure_id):
    return reverse('retrieve_update_delete_procedure', kwargs={'id': procedure_id})

def _create_payload(**overrides):
    base = {
        'name':     'Test Procedure',
        'category': 'restorative',
        'duration': 30,
        'price':    '150.00',
        'currency': '$',
        'branchId': None,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /procedures/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateProceduresAPIView:
    LIST_URL = 'list_create_procedures'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_procedures(
        self, api_client, admin_user, procedure_factory
    ):
        p1 = procedure_factory(name='Cleaning')
        p2 = procedure_factory(name='Whitening')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(p1.id) in ids
        assert str(p2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, procedure_factory
    ):
        procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"

    def test_admin_sees_procedures_from_all_branches(
        self, api_client, admin_user, procedure_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        p1 = procedure_factory(branch=b1)
        p2 = procedure_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(p1.id) in ids
        assert str(p2.id) in ids

    def test_dentist_list_filtered_by_own_branch(
        self, api_client, dentist_user, procedure_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        dentist_user.branches.set([b1])

        p_own   = procedure_factory(branch=b1)
        p_other = procedure_factory(branch=b2)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(p_own.id) in ids
        assert str(p_other.id) not in ids

    def test_dentist_sees_all_when_no_branches_exist(
        self, api_client, dentist_user, procedure_factory
    ):
        """filter_by_branch falls through to the full queryset when no Branch rows exist."""
        proc = procedure_factory()
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert str(proc.id) in [i['id'] for i in response.data['data']]

    def test_procedures_with_soft_deleted_branch_excluded(
        self, api_client, admin_user, procedure_factory, branch_factory
    ):
        """ProcedureManager: Q(branch__is_deleted=False) hides stale entries."""
        active = branch_factory()
        dying  = branch_factory()
        visible = procedure_factory(branch=active)
        hidden  = procedure_factory(branch=dying)

        dying.is_deleted = True
        dying.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    def test_procedure_with_null_branch_always_visible(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory(branch=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(proc.id) in [i['id'] for i in response.data['data']]

    def test_list_supports_search_by_name(
        self, api_client, admin_user, procedure_factory
    ):
        visible = procedure_factory(name='Teeth Whitening', category='cosmetic')
        procedure_factory(name='Extraction', category='surgical')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL), {'search': 'whitening'})

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert str(visible.id) in [i['id'] for i in response.data['data']]

    def test_list_supports_search_by_category(
        self, api_client, admin_user, procedure_factory
    ):
        visible = procedure_factory(name='Crown Fitting', category='prosthetic')
        procedure_factory(name='Checkup', category='diagnostic')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL), {'search': 'prosthetic'})

        ids = [i['id'] for i in response.data['data']]
        assert str(visible.id) in ids

    def test_receptionist_cannot_view_procedures(self, api_client, receptionist_user):
        """receptionist lacks 'view.procedures' by default."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_assistant_cannot_view_procedures(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_list_procedures(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_procedure(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Procedure.objects.filter(name='Test Procedure').exists()

    def test_create_response_is_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_create_with_explicit_branch(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(branchId=str(branch.id)),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        proc = Procedure.objects.get(name='Test Procedure')
        assert proc.branch == branch

    def test_create_without_branch_id_key_returns_400(self, api_client, admin_user):
        """branchId is required=True; omitting the key entirely → 400."""
        api_client.force_authenticate(user=admin_user)
        payload = _create_payload()
        payload.pop('branchId')
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_auto_assigns_branch_from_user_active_branch(
        self, api_client, admin_user, branch
    ):
        """ValidateBranchMixin: branchId=null + user.branch set → auto-assign."""
        admin_user.branch = branch
        admin_user.branches.add(branch)
        admin_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        proc = Procedure.objects.get(name='Test Procedure')
        assert proc.branch == branch

    def test_create_without_branch_id_returns_400_when_branches_exist_and_no_active_branch(
        self, api_client, dentist_user, branch
    ):
        """branches exist + no branchId + no active/assigned branch → 400."""
        api_client.force_authenticate(user=dentist_user)  #dentist user because admin gets any new branch added by default
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_invalid_category_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(category='not_a_real_category'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_negative_price_returns_400(self, api_client, admin_user):
        """Procedure.price has MinValueValidator(0)."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(price='-10.00'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_negative_duration_returns_400(self, api_client, admin_user):
        """Procedure.duration has MinValueValidator(0)."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(duration=-15),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_zero_duration_is_allowed(self, api_client, admin_user):
        """MinValueValidator(0) permits exactly 0 (boundary check)."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(duration=0),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_with_missing_required_fields_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.LIST_URL), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_dentist_can_create_procedure(self, api_client, dentist_user):
        """dentist has procedure permissions by default."""
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_receptionist_cannot_create_procedure(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_create_procedure(self, api_client):
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | PATCH | DELETE  /procedures/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteProcedureAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_procedure(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(proc.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['id'] == str(proc.id)

    def test_retrieve_response_includes_metadata(
        self, api_client, admin_user, procedure_factory
    ):
        """ProcedureSerializer inherits UserPermissionsMixin → metadata on GET."""
        proc = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(proc.id))

        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_user_in_procedures_branch_can_retrieve(
        self, api_client, dentist_user, procedure_factory, branch_factory
    ):
        b = branch_factory()
        dentist_user.branches.set([b])
        proc = procedure_factory(branch=b)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_detail_url(proc.id))
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_user_outside_procedures_branch_cannot_retrieve(
        self, api_client, dentist_user, procedure_factory, branch_factory
    ):
        """SystemBasePermission.has_object_permission: branch mismatch → 403."""
        b1 = branch_factory()
        b2 = branch_factory()
        dentist_user.branches.set([b1])
        proc = procedure_factory(branch=b2)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_detail_url(proc.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_procedure_with_null_branch_accessible_to_any_permitted_user(
        self, api_client, dentist_user, procedure_factory, branch_factory
    ):
        """has_object_permission: obj.branch_id is None → branch check skipped."""
        branch_factory()   # makes Branch.objects.exists() True
        proc = procedure_factory(branch=None)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_detail_url(proc.id))
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_nonexistent_procedure_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_unauthenticated_cannot_retrieve_procedure(self, api_client, procedure_factory):
        proc = procedure_factory()
        response = api_client.get(_detail_url(proc.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── UPDATE (PUT) ──────────────────────────────────────────────────────────

    def test_admin_can_full_update_procedure(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory(name='Scaling', duration=30, price='140.00')
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _detail_url(proc.id),
            {
                'name':     'Deep Scaling',
                'category': proc.category,
                'duration': 60,
                'price':    '220.00',
                'currency': '$',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        proc.refresh_from_db()
        assert proc.name == 'Deep Scaling'
        assert proc.duration == 60
        assert str(proc.price) == '220.00'

    def test_branch_id_is_read_only_on_update(
        self, api_client, admin_user, procedure_factory, branch_factory
    ):
        """UpdateProcedureSerializer: branchId is read_only."""
        original = branch_factory()
        new_branch = branch_factory()
        proc = procedure_factory(branch=original)

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _detail_url(proc.id), {'branchId': str(new_branch.id)}, format='json'
        )
        proc.refresh_from_db()
        assert proc.branch == original

    # ── UPDATE (PATCH) ────────────────────────────────────────────────────────

    def test_admin_can_partial_update_price(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory(price='100.00')
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(proc.id), {'price': '175.00'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        proc.refresh_from_db()
        assert str(proc.price) == '175.00'

    def test_partial_update_only_modifies_supplied_fields(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory(name='Original Name', duration=45)
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _detail_url(proc.id), {'duration': 90}, format='json'
        )
        proc.refresh_from_db()
        assert proc.duration == 90
        assert proc.name == 'Original Name'   # unchanged

    def test_update_with_negative_price_returns_400(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(proc.id), {'price': '-50.00'}, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_update_with_invalid_category_returns_400(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(proc.id), {'category': 'bogus'}, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_update_response_is_wrapped(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(proc.id), {'name': 'Renamed'}, format='json'
        )

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_outside_branch_cannot_update_procedure(
        self, api_client, dentist_user, procedure_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        dentist_user.branches.set([b1])
        proc = procedure_factory(branch=b2)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.patch(
            _detail_url(proc.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_receptionist_cannot_update_procedure(
        self, api_client, receptionist_user, procedure_factory
    ):
        proc = procedure_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            _detail_url(proc.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_update_procedure(self, api_client, procedure_factory):
        proc = procedure_factory()
        response = api_client.patch(
            _detail_url(proc.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_procedure(self, api_client, admin_user, procedure_factory):
        proc = procedure_factory()
        pid = proc.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_detail_url(pid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not Procedure.objects.filter(id=pid).exists()

    def test_delete_is_hard_delete(self, api_client, admin_user, procedure_factory):
        """Procedure has no own soft-delete flag — confirmed hard delete via all_objects."""
        proc = procedure_factory()
        pid = proc.id
        api_client.force_authenticate(user=admin_user)
        api_client.delete(_detail_url(pid))
        assert not Procedure.all_objects.filter(id=pid).exists()

    def test_user_outside_branch_cannot_delete_procedure(
        self, api_client, dentist_user, procedure_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        dentist_user.branches.set([b1])
        proc = procedure_factory(branch=b2)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.delete(_detail_url(proc.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_receptionist_cannot_delete_procedure(
        self, api_client, receptionist_user, procedure_factory
    ):
        proc = procedure_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.delete(_detail_url(proc.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_delete_procedure(self, api_client, procedure_factory):
        proc = procedure_factory()
        response = api_client.delete(_detail_url(proc.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_delete_nonexistent_procedure_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_detail_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /procedures/options
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveProcedureOptionsAPIView:
    """Plain generics.GenericAPIView — ResponseMixin NOT applied."""
    URL = 'procedures_options'

    def test_authenticated_user_gets_options(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'branchChoices' in response.data
        assert 'categoryChoices' in response.data

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'success' not in response.data

    def test_category_choices_cover_all_categories(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['categoryChoices']}
        expected = {c.value for c in Procedure.ProcedureCategory}
        assert returned == expected

    def test_branch_choices_reflect_existing_branches(
        self, api_client, admin_user, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = {str(c['branchId']) for c in response.data['branchChoices']}
        assert str(b1.id) in ids
        assert str(b2.id) in ids

    def test_non_admin_can_access_options(self, api_client, receptionist_user):
        """Options endpoint requires IsAuthenticated only, not procedure permissions."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)