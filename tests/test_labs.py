import uuid
import pytest
from django.urls import reverse
from rest_framework import status
from datetime import date, timedelta
from clinic.models import Lab, LabOrder


#LABS TESTS

# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /labs/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateLabsAPIView:
    URL = 'list_create_labs'

    #payload helper
    def _lab_payload(self, **overrides):
        """Minimal valid lab payload with optional field overrides."""
        base = {
            'name': 'Test Lab',
            'phone': '+20101234567',
            'address': '123 Test Street, Cairo',
            'contactPerson': 'Dr. Contact',
            'branchId': None,
        }
        base.update(overrides)
        return base


    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_labs(self, api_client, admin_user, lab_factory):
        lab1 = lab_factory()
        lab2 = lab_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(l['id']) for l in response.data['data']]
        assert str(lab1.id) in ids
        assert str(lab2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, lab_factory
    ):
        lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing top-level key: {key}"

    def test_list_pagination_has_required_fields(
        self, api_client, admin_user, lab_factory
    ):
        lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        pagination = response.data['pagination']
        for key in ('page', 'limit', 'total', 'totalPages', 'hasNext', 'hasPrev'):
            assert key in pagination, f"Missing pagination key: {key}"

    def test_list_page_size_is_50(self, api_client, admin_user, lab_factory):
        """ListCreateLabsAPIView.paginate_queryset sets page_size = 50."""
        lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.data['pagination']['limit'] == 50

    def test_list_metadata_includes_user_permissions(
        self, api_client, admin_user, lab_factory
    ):
        lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert 'userPermissions' in response.data['metadata']

    def test_admin_sees_labs_from_all_branches(
        self, api_client, admin_user, lab_factory, branch_factory
    ):
        """Admin bypasses FilterByBranchMixin and gets all labs."""
        b1 = branch_factory()
        b2 = branch_factory()
        lab1 = lab_factory(branch=b1)
        lab2 = lab_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [str(l['id']) for l in response.data['data']]
        assert str(lab1.id) in ids
        assert str(lab2.id) in ids

    def test_user_with_view_labs_can_list_when_no_branches_exist(
        self, api_client, assistant_user, lab_factory
    ):
        """With no Branch rows, filter_by_branch returns the full queryset."""
        lab = lab_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        assert str(lab.id) in [str(l['id']) for l in response.data['data']]

    def test_non_admin_list_is_filtered_by_user_branch(
        self, api_client, user_factory, lab_factory, branch_factory
    ):
        """
        Non-admin with view.labs and one assigned branch sees only that
        branch's labs (filter_by_branch: branches_count == 1 path).
        """
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='assistant')   # assistant has view.labs
        user.branches.set([b1])

        lab_own = lab_factory(branch=b1)
        lab_other = lab_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(l['id']) for l in response.data['data']]
        assert str(lab_own.id) in ids
        assert str(lab_other.id) not in ids

    def test_dentist_gets_branch_filtered_list(
        self, api_client, dentist_user, lab_factory, branch_factory
    ):
        """
        Dentist role is explicitly granted filtered access in get_queryset
        regardless of individual userPermissions.
        """
        b = branch_factory()
        dentist_user.branches.set([b])

        lab_own = lab_factory(branch=b)
        lab_other = lab_factory(branch=branch_factory())

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(l['id']) for l in response.data['data']]
        assert str(lab_own.id) in ids
        assert str(lab_other.id) not in ids

    def test_labs_with_soft_deleted_branch_are_excluded(
        self, api_client, admin_user, lab_factory, branch_factory
    ):
        """
        LabsManager: Q(branch__isnull=True) | Q(branch__is_deleted=False)
        ensures labs tied to a soft-deleted branch are invisible.
        """
        active_branch = branch_factory()
        dying_branch = branch_factory()

        lab_visible = lab_factory(branch=active_branch)
        lab_hidden = lab_factory(branch=dying_branch)

        dying_branch.is_deleted = True
        dying_branch.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [str(l['id']) for l in response.data['data']]
        assert str(lab_visible.id) in ids
        assert str(lab_hidden.id) not in ids

    def test_lab_with_null_branch_is_always_visible(
        self, api_client, admin_user, lab_factory
    ):
        """LabsManager Q(branch__isnull=True) keeps branch-less labs visible."""
        lab = lab_factory(branch=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [str(l['id']) for l in response.data['data']]
        assert str(lab.id) in ids

    def test_list_supports_search_by_name(
        self, api_client, admin_user, lab_factory
    ):
        target = lab_factory(name='Cairo Dental Lab')
        lab_factory(name='Alexandria Lab')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'search': 'Cairo'})

        assert response.status_code == status.HTTP_200_OK
        ids = [str(l['id']) for l in response.data['data']]
        assert str(target.id) in ids

    def test_user_without_view_labs_permission_gets_403(
        self, api_client, receptionist_user
    ):
        """receptionist default permissions do not include view.labs."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_list_labs(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_lab_with_explicit_branch(
        self, api_client, admin_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        payload = self._lab_payload(branchId=str(branch.id))
        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        created = Lab.objects.get(name='Test Lab')
        assert created.branch == branch

    def test_create_lab_without_branch_allowed_when_no_branches_exist(
        self, api_client, admin_user
    ):
        """ValidateBranchMixin: when Branch table is empty, branch=None is accepted."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._lab_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Lab.objects.get(name='Test Lab').branch is None

    def test_create_without_branch_id_auto_assigns_from_user_active_branch(
        self, api_client, admin_user, branch
    ):
        """ValidateBranchMixin: no branchId + user.branch set → auto-assign."""
        admin_user.branch = branch
        admin_user.branches.add(branch)
        admin_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._lab_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Lab.objects.get(name='Test Lab').branch == branch

    def test_create_without_branch_id_auto_assigns_from_sole_user_branch(
        self, api_client, user_factory, branch
    ):
        """ValidateBranchMixin: no branchId + user has exactly one branch → auto-assign."""
        user = user_factory(role='admin')
        user.branches.set([branch])

        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse(self.URL), self._lab_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Lab.objects.get(name='Test Lab').branch == branch

    def test_create_response_is_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._lab_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_create_response_does_not_include_metadata(self, api_client, admin_user):
        """UserPermissionsMixin only injects metadata on GET; POST response is plain."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._lab_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert 'metadata' not in response.data

    def test_create_with_missing_required_fields_returns_400(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.URL), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_invalid_phone_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._lab_payload(phone='not-a-phone'), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_with_only_view_permission_cannot_create_lab(
        self, api_client, assistant_user
    ):
        """assistant has view.labs but not create.lab; POST must be blocked."""
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            reverse(self.URL), self._lab_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_create_lab(self, api_client):
        response = api_client.post(
            reverse(self.URL), self._lab_payload(), format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# GET | PATCH | PUT | DELETE  /labs/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteLabAPIView:

    def _url(self, lab_id):
        return reverse('retrieve_update_delete_lab', kwargs={'id': lab_id})

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_any_lab(self, api_client, admin_user, lab_factory):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(lab.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['name'] == lab.name

    def test_retrieve_response_is_wrapped(self, api_client, admin_user, lab_factory):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(lab.id))

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_retrieve_response_includes_user_permissions_metadata(
        self, api_client, admin_user, lab_factory
    ):
        """UserPermissionsMixin injects metadata on detail GET only."""
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(lab.id))

        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_retrieve_includes_expected_fields(
        self, api_client, admin_user, lab_factory
    ):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(lab.id))

        data = response.data['data']
        for field in ('id', 'name', 'phone', 'address', 'contactPerson', 'branchId'):
            assert field in data, f"Missing field: {field}"

    def test_user_in_lab_branch_can_retrieve(
        self, api_client, user_factory, lab_factory, branch_factory
    ):
        b = branch_factory()
        user = user_factory(role='assistant')
        user.branches.set([b])
        lab = lab_factory(branch=b)

        api_client.force_authenticate(user=user)
        response = api_client.get(self._url(lab.id))
        assert response.status_code == status.HTTP_200_OK

    def test_user_not_in_lab_branch_cannot_retrieve(
        self, api_client, user_factory, lab_factory, branch_factory
    ):
        """
        SystemBasePermission.has_object_permission: user.branches must contain
        the lab's branch; mismatch → 403.
        """
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='assistant')
        user.branches.set([b1])
        lab = lab_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.get(self._url(lab.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_lab_with_null_branch_accessible_to_any_authenticated_user(
        self, api_client, user_factory, lab_factory, branch_factory
    ):
        """
        SystemBasePermission: obj.branch_id is None → branch membership check
        is skipped entirely → has_object_permission returns True.
        """
        branch_factory()                        # makes Branch.objects.exists() True
        user = user_factory(role='assistant')   # has view.labs
        lab = lab_factory(branch=None)

        api_client.force_authenticate(user=user)
        response = api_client.get(self._url(lab.id))
        assert response.status_code == status.HTTP_200_OK

    def test_nonexistent_lab_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_cannot_retrieve_lab(self, api_client, lab_factory):
        lab = lab_factory()
        response = api_client.get(self._url(lab.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── UPDATE (PATCH) ────────────────────────────────────────────────────────

    def test_admin_can_partial_update_lab(
        self, api_client, admin_user, lab_factory
    ):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(lab.id), {'name': 'Renamed Lab'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        lab.refresh_from_db()
        assert lab.name == 'Renamed Lab'

    def test_partial_update_only_modifies_supplied_fields(
        self, api_client, admin_user, lab_factory
    ):
        lab = lab_factory(contactPerson='Original Contact')
        original_address = lab.address

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            self._url(lab.id), {'contactPerson': 'Updated Contact'}, format='json'
        )

        lab.refresh_from_db()
        assert lab.contactPerson == 'Updated Contact'
        assert lab.address == original_address   # unchanged

    def test_update_cannot_change_branch(
        self, api_client, admin_user, lab_factory, branch_factory
    ):
        """
        UpdateLabSerializer.branchId is read_only; sending a new
        branchId in the PATCH payload must be silently ignored.
        """
        original_branch = branch_factory()
        new_branch = branch_factory()
        lab = lab_factory(branch=original_branch)

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            self._url(lab.id),
            {'branchId': str(new_branch.id)},
            format='json',
        )

        lab.refresh_from_db()
        assert lab.branch == original_branch

    def test_update_with_invalid_phone_returns_400(
        self, api_client, admin_user, lab_factory
    ):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(lab.id), {'phone': 'not-a-phone'}, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_response_is_wrapped(self, api_client, admin_user, lab_factory):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(lab.id), {'name': 'Updated'}, format='json'
        )

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_not_in_lab_branch_cannot_update(
        self, api_client, user_factory, lab_factory, branch_factory
    ):
        """has_object_permission blocks updates by users outside the lab's branch."""
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='assistant')
        user.branches.set([b1])
        lab = lab_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.patch(
            self._url(lab.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_without_update_permission_cannot_update_lab(
        self, api_client, assistant_user, lab_factory
    ):
        """assistant has view.labs but not update.lab → blocked at has_permission."""
        lab = lab_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.patch(
            self._url(lab.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_update_lab(self, api_client, lab_factory):
        lab = lab_factory()
        response = api_client.patch(
            self._url(lab.id), {'name': 'Hijacked'}, format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── UPDATE (PUT) ──────────────────────────────────────────────────────────

    def test_admin_can_full_update_lab(self, api_client, admin_user, lab_factory):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        payload = {
            'name': 'Fully Updated Lab',
            'phone': '+20109999888',
            'address': '999 New Street, Giza',
            'contactPerson': 'New Person',
            'notes': 'Updated notes',
        }
        response = api_client.put(self._url(lab.id), payload, format='json')

        assert response.status_code == status.HTTP_200_OK
        lab.refresh_from_db()
        assert lab.name == 'Fully Updated Lab'
        assert lab.contactPerson == 'New Person'

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_lab(self, api_client, admin_user, lab_factory):
        lab = lab_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(lab.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_is_hard_delete(self, api_client, admin_user, lab_factory):
        """
        RetrieveUpdateDeleteLabAPIView has no custom destroy; DRF's default
        DestroyModelMixin performs a hard delete (no soft-delete on Lab).
        """
        lab = lab_factory()
        lid = lab.id
        api_client.force_authenticate(user=admin_user)
        api_client.delete(self._url(lid))

        # Must be absent from both managers
        assert not Lab.objects.filter(id=lid).exists()
        assert not Lab.all_objects.filter(id=lid).exists()

    def test_user_without_delete_permission_cannot_delete_lab(
        self, api_client, assistant_user, lab_factory
    ):
        """assistant has view.labs but not delete.lab → 403 at has_permission."""
        lab = lab_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.delete(self._url(lab.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_delete_lab(self, api_client, lab_factory):
        lab = lab_factory()
        response = api_client.delete(self._url(lab.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_nonexistent_lab_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND



##################################################


#LAB ORDERS TESTS

# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /lab-orders/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateLabOrdersAPIView:
    URL = 'list_create_lab_orders'

    # ── payload helper (method, not module-level, to keep test isolation) ─────

    def _payload(self, lab, patient, procedure, **overrides):
        base = {
            'labId':       str(lab.id),
            'patientId':   str(patient.id),
            'procedureId': str(procedure.id),
            'toothNumber': '11',
            'sentDate':    str(date.today()),
            'dueDate':     str(date.today() + timedelta(days=7)),
            'cost':        '150.00',
            'currency':    '$',
            'branchId': None
        }
        base.update(overrides)
        return base

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_lab_orders(
        self, api_client, admin_user, lab_order_factory
    ):
        order1 = lab_order_factory()
        order2 = lab_order_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(o['id']) for o in response.data['data']]
        assert str(order1.id) in ids
        assert str(order2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, lab_order_factory
    ):
        lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"

    def test_list_metadata_includes_user_permissions(
        self, api_client, admin_user, lab_order_factory
    ):
        lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert 'userPermissions' in response.data['metadata']

    def test_admin_sees_orders_from_all_branches(
        self, api_client, admin_user, lab_order_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        o1 = lab_order_factory(branch=b1)
        o2 = lab_order_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [str(o['id']) for o in response.data['data']]
        assert str(o1.id) in ids
        assert str(o2.id) in ids

    def test_user_with_view_lab_orders_can_list_when_no_branches_exist(
        self, api_client, assistant_user, lab_order_factory
    ):
        """With no Branch rows, filter_by_branch returns the full queryset."""
        order = lab_order_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        assert str(order.id) in [str(o['id']) for o in response.data['data']]

    def test_non_admin_list_filtered_by_user_branch(
        self, api_client, user_factory, lab_order_factory, branch_factory
    ):
        """Non-admin with one assigned branch sees only that branch's orders."""
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='assistant')
        user.branches.set([b1])

        order_own   = lab_order_factory(branch=b1)
        order_other = lab_order_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(o['id']) for o in response.data['data']]
        assert str(order_own.id) in ids
        assert str(order_other.id) not in ids

    def test_orders_with_soft_deleted_branch_are_excluded(
        self, api_client, admin_user, lab_order_factory, branch_factory
    ):
        """
        LabOrdersManager: Q(branch__is_deleted=False) hides orders whose
        branch has been soft-deleted.
        """
        active = branch_factory()
        dying  = branch_factory()
        visible = lab_order_factory(branch=active)
        hidden  = lab_order_factory(branch=dying)

        dying.is_deleted = True
        dying.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [str(o['id']) for o in response.data['data']]
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    def test_order_with_null_branch_is_always_visible(
        self, api_client, admin_user, lab_order_factory
    ):
        """LabOrdersManager Q(branch__isnull=True) keeps branch-less orders visible."""
        order = lab_order_factory(branch=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert str(order.id) in [str(o['id']) for o in response.data['data']]

    def test_list_supports_search_by_lab_name(
        self, api_client, admin_user, lab_factory, lab_order_factory
    ):
        target_lab = lab_factory(name='Unique Ceramics Lab')
        other_lab  = lab_factory(name='Other Lab')
        target_order = lab_order_factory(lab=target_lab)
        lab_order_factory(lab=other_lab)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'search': 'Unique Ceramics'})

        assert response.status_code == status.HTTP_200_OK
        ids = [str(o['id']) for o in response.data['data']]
        assert str(target_order.id) in ids

    def test_user_without_view_lab_orders_permission_gets_403(
        self, api_client, receptionist_user
    ):
        """receptionist lacks view.labOrders in default permissions."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_list_lab_orders(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_lab_order(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert LabOrder.objects.filter(lab=lab, patient=patient).exists()

    def test_create_auto_sets_snapshot_fields(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        """labName, patientName, procedureName must be captured from FKs on save()."""
        lab     = lab_factory(name='Porcelain Lab')
        patient = patient_factory(name='Test Patient Snapshot')
        proc    = procedure_factory(name='Crown Procedure')

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )
        
        #fetch data for testing
        data = response.data['data']

        assert response.status_code == status.HTTP_201_CREATED
        assert data['labName']       == 'Porcelain Lab'
        assert data['patientName']   == 'Test Patient Snapshot'
        assert data['procedureName'] == 'Crown Procedure'

        #Verify persistence in the DB as well
        order = LabOrder.objects.get(id=data['id'])
        assert order.labName       == 'Porcelain Lab'
        assert order.patientName   == 'Test Patient Snapshot'
        assert order.procedureName == 'Crown Procedure'

    def test_create_defaults_status_to_sent(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        """LabOrder.save() sets status = 'sent' when none is supplied."""
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        order = LabOrder.objects.get(lab=lab, patient=patient)
        assert order.status == LabOrder.OrderStatusChoices.SENT

    def test_create_with_explicit_status(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc, status='in_production'),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        order = LabOrder.objects.get(lab=lab, patient=patient)
        assert order.status == LabOrder.OrderStatusChoices.IN_PRODUCTION

    def test_create_without_branch_id_allowed_when_no_branches_exist(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        """ValidateBranchMixin: empty Branch table → branch=None is accepted."""
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert LabOrder.objects.get(lab=lab, patient=patient).branch is None

    def test_create_without_branch_id_and_nonadmin_returns_400_when_branches_exist(
        self, api_client, assistant_user, lab_factory, patient_factory, procedure_factory,
        branch
    ):
        """ValidateBranchMixin: branches exist + no branchId + non-admin + no active branch → 400."""
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()
        
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_auto_assigns_branch_from_user_active_branch(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory,
        branch
    ):
        """ValidateBranchMixin: user.branch set + no branchId in payload → auto-assign."""
        admin_user.branch = branch
        admin_user.branches.add(branch)
        admin_user.save(update_fields=['branch', 'updatedAt'])

        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert LabOrder.objects.get(lab=lab, patient=patient).branch == branch

    def test_user_with_create_lab_order_permission_can_create(
        self, api_client, assistant_user, lab_factory, patient_factory, procedure_factory
    ):
        """assistant has create.labOrder by default; no branches exist so branch=None."""
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_response_is_wrapped(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_create_response_excludes_metadata(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        """UserPermissionsMixin only injects metadata on GET; POST skips it."""
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert 'metadata' not in response.data

    def test_create_with_missing_required_fields_returns_400(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.URL), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_invalid_tooth_number_returns_400(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc, toothNumber='99'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_without_create_permission_cannot_create(
        self, api_client, receptionist_user, lab_factory, patient_factory, procedure_factory
    ):
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_create_lab_order(
        self, api_client, lab_factory, patient_factory, procedure_factory
    ):
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        response = api_client.post(
            reverse(self.URL),
            self._payload(lab, patient, proc),
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# PATCH | DELETE  /lab-orders/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateDeleteLabOrderAPIView:

    def _url(self, order_id):
        return reverse('update_delete_lab_orders', kwargs={'id': order_id})

    # ── routing ───────────────────────────────────────────────────────────────

    def test_get_method_not_allowed(self, api_client, admin_user, lab_order_factory):
        """GET is excluded from http_method_names → 405."""
        order = lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(order.id))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # ── UPDATE (PATCH) ────────────────────────────────────────────────────────

    def test_admin_can_update_status(self, api_client, admin_user, lab_order_factory):
        order = lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(order.id), {'status': 'in_production'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.status == LabOrder.OrderStatusChoices.IN_PRODUCTION

    def test_admin_can_update_due_date(self, api_client, admin_user, lab_order_factory):
        order = lab_order_factory()
        new_due = str(date.today() + timedelta(days=21))

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(order.id), {'dueDate': new_due}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert str(order.dueDate) == new_due

    def test_admin_can_update_cost(self, api_client, admin_user, lab_order_factory):
        order = lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(order.id), {'cost': '999.00'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert str(order.cost) == '999.00'

    def test_admin_can_update_instructions(
        self, api_client, admin_user, lab_order_factory
    ):
        order = lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(order.id), {'instructions': 'Use shade A2, metal-free'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.instructions == 'Use shade A2, metal-free'

    def test_read_only_fields_are_ignored_on_update(
        self, api_client, admin_user, lab_order_factory, lab_factory
    ):
        """
        UpdateLabOrderSerializer marks labId, patientId, procedureId, toothNumber,
        sentDate, currency, branchId as read_only. Sending them must have no effect.
        """
        order = lab_order_factory()
        different_lab = lab_factory()
        original_tooth    = order.toothNumber
        original_sent_str = str(order.sentDate)

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            self._url(order.id),
            {
                'labId':       str(different_lab.id),
                'toothNumber': '21',
                'sentDate':    '2000-01-01',
            },
            format='json',
        )

        order.refresh_from_db()
        assert order.toothNumber    == original_tooth
        assert str(order.sentDate)  == original_sent_str
        assert order.lab            != different_lab

    def test_status_delivered_sets_delivered_date(
        self, api_client, admin_user, lab_order_factory
    ):
        order = lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(order.id), {'status': 'delivered'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.deliveredDate == date.today()

    def test_status_received_sets_received_date(
        self, api_client, admin_user, lab_order_factory
    ):
        order = lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(order.id), {'status': 'received'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.receivedDate == date.today()

    def test_update_response_is_wrapped(self, api_client, admin_user, lab_order_factory):
        order = lab_order_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(order.id), {'status': 'in_production'}, format='json'
        )

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_user_with_update_lab_order_permission_can_update(
        self, api_client, assistant_user, lab_order_factory
    ):
        """assistant has update.labOrder by default."""
        order = lab_order_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.patch(
            self._url(order.id), {'status': 'in_production'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK

    def test_user_not_in_lab_order_branch_cannot_update(
        self, api_client, user_factory, lab_order_factory, branch_factory
    ):
        """SystemBasePermission.has_object_permission blocks cross-branch updates."""
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='assistant')
        user.branches.set([b1])
        order = lab_order_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.patch(
            self._url(order.id), {'status': 'in_production'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_without_update_permission_cannot_update(
        self, api_client, receptionist_user, lab_order_factory
    ):
        """receptionist lacks update.labOrder → blocked at has_permission."""
        order = lab_order_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            self._url(order.id), {'status': 'in_production'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_update_lab_order(
        self, api_client, lab_order_factory
    ):
        order = lab_order_factory()
        response = api_client.patch(
            self._url(order.id), {'status': 'in_production'}, format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_nonexistent_lab_order_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            self._url(uuid.uuid4()), {'status': 'in_production'}, format='json'
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_lab_order(self, api_client, admin_user, lab_order_factory):
        order = lab_order_factory()
        oid = order.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(oid))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Lab has no soft-delete — must be absent from both managers
        assert not LabOrder.objects.filter(id=oid).exists()
        assert not LabOrder.all_objects.filter(id=oid).exists()

    def test_user_without_delete_permission_cannot_delete(
        self, api_client, assistant_user, lab_order_factory
    ):
        """assistant has update.labOrder but not delete.labOrder."""
        order = lab_order_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.delete(self._url(order.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_delete_lab_order(
        self, api_client, lab_order_factory
    ):
        order = lab_order_factory()
        response = api_client.delete(self._url(order.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_nonexistent_lab_order_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════════════
# GET  /lab-orders/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveLabOrdersOptionsAPIView:
    """
    RetrieveLabOrdersOptionsAPIView inherits from plain generics.GenericAPIView
    — NOT from the project's base view — so ResponseMixin is NOT applied.
    The response is a bare dict.
    """
    URL = 'lab_orders_options'

    def test_authenticated_user_gets_full_options_payload(
        self, api_client, assistant_user
    ):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        for key in ('branchChoices', 'labChoices', 'patientChoices',
                    'procedureChoices', 'orderStatus', 'validToothNumbers'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped_by_response_mixin(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert 'success' not in response.data
        assert 'data'    not in response.data

    def test_order_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['orderStatus']}
        expected = {c.value for c in LabOrder.OrderStatusChoices}
        assert returned == expected

    def test_order_status_choices_have_value_and_label_keys(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        for choice in response.data['orderStatus']:
            assert 'value' in choice
            assert 'label' in choice

    def test_valid_tooth_numbers_are_non_empty_and_have_value_label(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        teeth = response.data['validToothNumbers']
        assert len(teeth) > 0
        for tooth in teeth:
            assert 'value' in tooth
            assert 'label' in tooth

    def test_branch_choices_always_include_all_branches(
        self, api_client, admin_user, branch_factory
    ):
        """branchChoices is never filtered by branchId."""
        b1 = branch_factory()
        b2 = branch_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned_ids = {str(c['branchId']) for c in response.data['branchChoices']}
        assert str(b1.id) in returned_ids
        assert str(b2.id) in returned_ids

    def test_lab_patient_procedure_choices_empty_when_branches_exist_but_no_branch_id(
        self, api_client, admin_user, branch_factory, lab_factory, patient_factory,
        procedure_factory
    ):
        """
        get_labChoices / get_patientChoices / get_procedureChoices:
        'if not branchId and Branch.objects.exists(): return []'
        Guards against returning unfiltered cross-branch data.
        """
        b = branch_factory()
        lab_factory(branch=b)
        patient_factory(branch=b)
        procedure_factory(branch=b)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))   # no branchId QP

        assert response.data['labChoices']       == []
        assert response.data['patientChoices']   == []
        assert response.data['procedureChoices'] == []

    def test_choices_filtered_by_branch_id_query_param(
        self, api_client, admin_user, branch_factory, lab_factory, patient_factory,
        procedure_factory
    ):
        """Providing ?branchId filters all three choice sets to that branch."""
        b1 = branch_factory()
        b2 = branch_factory()

        lab_b1     = lab_factory(branch=b1)
        patient_b1 = patient_factory(branch=b1)
        proc_b1    = procedure_factory(branch=b1)
        lab_b2     = lab_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        assert response.status_code == status.HTTP_200_OK

        lab_ids     = {str(c['labId'])       for c in response.data['labChoices']}
        patient_ids = {str(c['patientId'])   for c in response.data['patientChoices']}
        proc_ids    = {str(c['procedureId']) for c in response.data['procedureChoices']}

        assert str(lab_b1.id)     in lab_ids
        assert str(lab_b2.id)     not in lab_ids
        assert str(patient_b1.id) in patient_ids
        assert str(proc_b1.id)    in proc_ids

    def test_choices_show_all_when_no_branches_exist(
        self, api_client, admin_user, lab_factory, patient_factory, procedure_factory
    ):
        """With no Branch rows: filters = {} → all labs/patients/procedures returned."""
        lab     = lab_factory()
        patient = patient_factory()
        proc    = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert str(lab.id)     in {str(c['labId'])       for c in response.data['labChoices']}
        assert str(patient.id) in {str(c['patientId'])   for c in response.data['patientChoices']}
        assert str(proc.id)    in {str(c['procedureId']) for c in response.data['procedureChoices']}

    def test_nonexistent_branch_id_query_param_returns_400(
        self, api_client, admin_user
    ):
        """BranchToSerializerMixin raises ValidationError for unknown branchId."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_admin_can_access_options(self, api_client, assistant_user):
        """Options endpoint requires IsAuthenticated only."""
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

