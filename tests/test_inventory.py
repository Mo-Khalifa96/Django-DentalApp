import uuid
import pytest
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from clinic.models import Inventory


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detail_url(item_id):
    return reverse('retrieve_update_delete_inventory', kwargs={'id': item_id})

def _create_payload(**overrides):
    base = {
        'name':         'Test Item',
        'category':     'Consumables',
        'currentStock': 10,
        'minStock':     5,
        'unit':         'pcs',
        'supplier':     'Acme Supplies',
        'branchId':     None,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /inventory/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateInventoryAPIView:
    LIST_URL = 'list_create_inventory'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_inventory(
        self, api_client, admin_user, inventory_factory
    ):
        i1 = inventory_factory(name='Gloves')
        i2 = inventory_factory(name='Masks')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(i1.id) in ids
        assert str(i2.id) in ids

    def test_list_page_size_is_50(self, api_client, admin_user, inventory_factory):
        inventory_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.data['pagination']['limit'] == 50

    def test_assistant_can_list_with_low_stock_filter(
        self, api_client, assistant_user, inventory_factory
    ):
        low_stock = inventory_factory(
            name='Gloves', category='Consumables', currentStock=2, minStock=10,
        )
        inventory_factory(
            name='Masks', category='Consumables', currentStock=20, minStock=5,
        )

        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(
            reverse(self.LIST_URL), {'lowStock': 'true', 'category': 'Consumables'}
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert [i['id'] for i in response.data['data']] == [str(low_stock.id)]

    def test_dentist_list_filtered_by_own_branch(
        self, api_client, dentist_user, inventory_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        dentist_user.branches.set([b1])
        dentist_user.userPermissions.append('view.inventory')
        dentist_user.save(update_fields=['userPermissions'])

        item_own   = inventory_factory(branch=b1)
        item_other = inventory_factory(branch=b2)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(item_own.id) in ids
        assert str(item_other.id) not in ids

    def test_items_with_soft_deleted_branch_excluded(
        self, api_client, admin_user, inventory_factory, branch_factory
    ):
        active = branch_factory()
        dying  = branch_factory()
        visible = inventory_factory(branch=active)
        hidden  = inventory_factory(branch=dying)

        dying.is_deleted = True
        dying.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    def test_receptionist_cannot_access_inventory(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_list_inventory(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_assistant_can_create_inventory_item(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Inventory.objects.filter(name='Test Item').exists()

    def test_create_auto_sets_last_ordered(self, api_client, admin_user):
        """Inventory.save(): lastOrdered defaults to today when not provided."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        item = Inventory.objects.get(id=response.data['data']['id'])
        assert item.lastOrdered is not None

    def test_create_without_branch_id_key_returns_400(self, api_client, admin_user):
        """branchId is required=True; omitting the key entirely → 400."""
        api_client.force_authenticate(user=admin_user)
        payload = _create_payload()
        payload.pop('branchId')
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_explicit_branch(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(branchId=str(branch.id)),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        item = Inventory.objects.get(name='Test Item')
        assert item.branch == branch

    def test_create_with_missing_required_fields_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.LIST_URL), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_receptionist_cannot_create_inventory_item(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_create_inventory_item(self, api_client):
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | PATCH | DELETE  /inventory/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteInventoryAPIView:

    def test_admin_can_retrieve_item(self, api_client, admin_user, inventory_factory):
        item = inventory_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(item.id))
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['id'] == str(item.id)

    def test_user_outside_branch_cannot_retrieve_item(
        self, api_client, assistant_user, inventory_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        assistant_user.branches.set([b1])
        item = inventory_factory(branch=b2)

        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(_detail_url(item.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_nonexistent_item_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_admin_can_update_stock_levels(
        self, api_client, admin_user, inventory_factory
    ):
        item = inventory_factory(currentStock=6, minStock=3, unit='boxes')
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _detail_url(item.id),
            {
                'name': item.name, 'category': item.category,
                'currentStock': 12, 'minStock': 5,
                'unit': item.unit, 'supplier': item.supplier,
                'lastOrdered': item.lastOrdered.isoformat(),
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        item.refresh_from_db()
        assert item.currentStock == 12
        assert item.minStock == 5

    def test_branch_id_is_read_only_on_update(
        self, api_client, admin_user, inventory_factory, branch_factory
    ):
        original = branch_factory()
        new_branch = branch_factory()
        item = inventory_factory(branch=original)

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _detail_url(item.id), {'branchId': str(new_branch.id)}, format='json'
        )
        item.refresh_from_db()
        assert item.branch == original

    def test_partial_update_only_modifies_supplied_fields(
        self, api_client, admin_user, inventory_factory
    ):
        item = inventory_factory(supplier='Original Supplier', currentStock=10)
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _detail_url(item.id), {'currentStock': 25}, format='json'
        )
        item.refresh_from_db()
        assert item.currentStock == 25
        assert item.supplier == 'Original Supplier'

    def test_receptionist_cannot_update_inventory(
        self, api_client, receptionist_user, inventory_factory
    ):
        item = inventory_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            _detail_url(item.id), {'currentStock': 99}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_admin_can_delete_item(self, api_client, admin_user, inventory_factory):
        item = inventory_factory()
        iid = item.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_detail_url(iid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not Inventory.objects.filter(id=iid).exists()

    def test_delete_is_hard_delete(self, api_client, admin_user, inventory_factory):
        """Inventory has no own soft-delete flag — confirmed via all_objects."""
        item = inventory_factory()
        iid = item.id
        api_client.force_authenticate(user=admin_user)
        api_client.delete(_detail_url(iid))
        assert not Inventory.all_objects.filter(id=iid).exists()

    def test_receptionist_cannot_delete_inventory(
        self, api_client, receptionist_user, inventory_factory
    ):
        item = inventory_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.delete(_detail_url(item.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_delete_item(self, api_client, inventory_factory):
        item = inventory_factory()
        response = api_client.delete(_detail_url(item.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /inventory/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveInventoryOptionsAPIView:
    URL = 'inventory_options'

    def test_authenticated_user_gets_options(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'categoryChoices', 'unitChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        assert 'success' not in api_client.get(reverse(self.URL)).data

    def test_category_choices_are_distinct_and_sorted(
        self, api_client, admin_user, inventory_factory
    ):
        inventory_factory(category='Consumables')
        inventory_factory(category='Consumables')
        inventory_factory(category='Equipment')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert list(response.data['categoryChoices']) == [
            {'value': 'Consumables', 'label': 'Consumables'},
            {'value': 'Equipment', 'label': 'Equipment'},
        ]

    def test_category_choices_filtered_by_branch_id(
        self, api_client, admin_user, inventory_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        inventory_factory(branch=b1, category='Consumables')
        inventory_factory(branch=b2, category='Equipment')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        values = [c['value'] for c in response.data['categoryChoices']]
        assert values == ['Consumables']

    def test_category_choices_empty_when_branches_exist_and_no_branch_id(
        self, api_client, admin_user, branch_factory, inventory_factory
    ):
        b = branch_factory()
        inventory_factory(branch=b)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['categoryChoices'] == []

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)