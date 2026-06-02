import pytest
from django.urls import reverse
from rest_framework import status

from clinic.models import Procedure


pytestmark = pytest.mark.django_db


class TestProceduresAPI:
    def test_list_procedures_supports_search_and_category_filter(
        self,
        api_client,
        admin_user,
        procedure_factory,
    ):
        visible = procedure_factory(name='Teeth Whitening', category='Cosmetic')
        procedure_factory(name='extraction', category='surgical')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(
            reverse('list_create_procedures'),
            {'search': 'whitening', 'category': 'cosmetic'},
        )

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['data']] == [str(visible.id)]

    def test_receptionist_cannot_view_procedures(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse('list_create_procedures'))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_procedure_persists_valid_payload(self, api_client, admin_user):
        payload = {
            'name': 'Composite Filling',
            'category': 'restorative',
            'duration': 45,
            'price': '320.00',
            'currency': '$',
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse('list_create_procedures'), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == payload['name']
        assert Procedure.objects.filter(name='Composite Filling').exists()

    def test_update_procedure_changes_editable_fields(
        self,
        api_client,
        admin_user,
        procedure_factory,
    ):
        procedure = procedure_factory(name='Scaling', duration=30, price='140.00')

        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            reverse('retrieve_update_delete_procedure', kwargs={'id': procedure.id}),
            {
                'name': 'Deep Scaling',
                'category': procedure.category,
                'duration': 60,
                'price': '220.00',
                'currency': '$',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        procedure.refresh_from_db()
        assert procedure.name == 'Deep Scaling'
        assert procedure.duration == 60

    def test_delete_procedure_removes_record(self, api_client, admin_user, procedure_factory):
        procedure = procedure_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(
            reverse('retrieve_update_delete_procedure', kwargs={'id': procedure.id})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Procedure.objects.filter(id=procedure.id).exists()
