import pytest
from django.urls import reverse
from rest_framework import status

from clinic.models import Inventory


pytestmark = pytest.mark.django_db


class TestInventoryAPI:
    def test_assistant_can_list_inventory_with_low_stock_filter(
        self,
        api_client,
        assistant_user,
        inventory_factory,
    ):
        low_stock_item = inventory_factory(
            name='Gloves',
            category='Consumables',
            currentStock=2,
            minStock=10,
        )
        inventory_factory(
            name='Masks',
            category='Consumables',
            currentStock=20,
            minStock=5,
        )

        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(
            reverse('list_create_inventory'),
            {'lowStock': 'true', 'category': 'Consumables'},
        )

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['data']] == [str(low_stock_item.id)]

    def test_receptionist_cannot_access_inventory(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse('list_create_inventory'))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_inventory_item_sets_last_ordered(self, api_client, admin_user):
        payload = {
            'name': 'Composite Resin',
            'category': 'Materials',
            'currentStock': 15,
            'minStock': 4,
            'unit': 'packs',
            'supplier': 'Dental Supply Co',
            'branchId': None,
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse('list_create_inventory'), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        item = Inventory.objects.get(id=response.data['data']['id'])
        assert item.name == payload['name']
        assert item.lastOrdered is not None

    def test_update_inventory_item_changes_stock_levels(
        self,
        api_client,
        admin_user,
        inventory_factory,
    ):
        item = inventory_factory(currentStock=6, minStock=3, unit='boxes')

        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            reverse('retrieve_update_delete_inventory', kwargs={'id': item.id}),
            {
                'name': item.name,
                'category': item.category,
                'currentStock': 12,
                'minStock': 5,
                'unit': item.unit,
                'supplier': item.supplier,
                'lastOrdered': item.lastOrdered.isoformat(),
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.currentStock == 12
        assert item.minStock == 5

    def test_delete_inventory_item_removes_record(self, api_client, admin_user, inventory_factory):
        item = inventory_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(
            reverse('retrieve_update_delete_inventory', kwargs={'id': item.id})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Inventory.objects.filter(id=item.id).exists()

    def test_inventory_options_returns_distinct_categories(
        self,
        api_client,
        admin_user,
        inventory_factory,
    ):
        inventory_factory(category='Consumables')
        inventory_factory(category='Equipment')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse('inventory_options'))

        assert response.status_code == status.HTTP_200_OK
        assert list(response.data['categoryChoices']) == [
            {'value': 'Consumables', 'label': 'Consumables'},
            {'value': 'Equipment', 'label': 'Equipment'},
        ]
