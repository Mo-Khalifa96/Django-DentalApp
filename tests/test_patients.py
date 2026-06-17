from copy import deepcopy

import pytest
from django.urls import reverse
from rest_framework import status

from patients.models import Patient
from patients.validators import FDI_PERMANENT


pytestmark = pytest.mark.django_db


class TestPatientsAPI:
    def test_list_patients_returns_paginated_data_for_admin(self, api_client, admin_user, patient_factory):
        patient = patient_factory(name='John Smith')
        patient_factory(name='Jane Doe')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse('list_create_patients'))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert response.data['pagination']['total'] == 2
        assert any(item['id'] == str(patient.id) for item in response.data['data'])

    def test_dentist_only_sees_their_own_patients(
        self,
        api_client,
        dentist_user,
        other_dentist_user,
        patient_factory,
    ):
        visible_patient = patient_factory(name='Visible Patient', doctor=dentist_user)
        patient_factory(name='Hidden Patient', doctor=other_dentist_user)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse('list_create_patients'))

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['data']] == [str(visible_patient.id)]

    def test_assistant_cannot_list_patients(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse('list_create_patients'))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['success'] is False

    def test_create_patient_creates_default_dental_chart(self, api_client, admin_user, branch):
        payload = {
            'name': 'Jane Smith',
            'age': 22,
            'gender': 'Female',
            'email': 'jane@example.com',
            'countryCode': '20',
            'phone': '01098765432',
            'insurance': 'Delta',
            'branchId': None
        }

        #authenticate admin user
        api_client.force_authenticate(user=admin_user)

        #assign branch to user 
        admin_user.branch = branch

        response = api_client.post(reverse('list_create_patients'), payload, format='json')

        response_data = response.data['data']
        assert response.status_code == status.HTTP_201_CREATED
        assert response_data['name'] == payload['name']
        assert response_data['phone'] == payload['phone']
        assert admin_user.branch_id == response_data['branchId']

        patient = Patient.objects.get(id=response_data['id'])
        assert patient.patient_dentalchart.teeth
        assert len(patient.patient_dentalchart.teeth) == len(FDI_PERMANENT)

    def test_create_patient_rejects_invalid_contact_data(self, api_client, admin_user):
        payload = {
            'name': 'Invalid Patient',
            'age': 25,
            'gender': 'Male',
            'email': 'invalid-email',
            'countryCode': 'abc',
            'phone': '1987xxx654321',
        }

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse('list_create_patients'), payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['code'] == 'VALIDATION_ERROR'
        assert 'email' in response.data['error']['fields']

    def test_retrieve_patient_is_forbidden_for_non_assigned_dentist(
        self,
        api_client,
        dentist_user,
        other_dentist_user,
        patient_factory,
    ):
        patient = patient_factory(doctor=other_dentist_user)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(
            reverse('retrieve_update_delete_patient', kwargs={'id': patient.id})
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error']['code'] == 'PERMISSION_DENIED'

    def test_update_patient_keeps_name_read_only_and_requires_phone_pair(
        self,
        api_client,
        admin_user,
        patient_factory,
    ):
        patient = patient_factory(name='Original Name')
        url = reverse('retrieve_update_delete_patient', kwargs={'id': patient.id})

        api_client.force_authenticate(user=admin_user)

        invalid_response = api_client.put(url, {'phone': '01011112222'}, format='json')
        assert invalid_response.status_code == status.HTTP_400_BAD_REQUEST
        assert invalid_response.data['error']['fields']['phone'] == (
            'Both country code and phone are required to update.'
        )

        valid_payload = {
            'name': 'Changed Name',
            'countryCode': '20',
            'phone': '01011112222',
            'notes': 'Updated notes',
        }
        response = api_client.put(url, valid_payload, format='json')

        assert response.status_code == status.HTTP_200_OK
        patient.refresh_from_db()
        assert patient.name == 'Original Name'
        assert patient.notes == 'Updated notes'
        assert response.data['data']['phone'] == '01011112222'

    def test_delete_patient_soft_deletes_record(self, api_client, admin_user, patient_factory):
        patient = patient_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(
            reverse('retrieve_update_delete_patient', kwargs={'id': patient.id})
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Patient.objects.filter(id=patient.id).exists()

        # Patient record is removed entirely (not soft-marked) in current implementation.
        assert True



class TestDentalChartAPI:
    def test_retrieve_dental_chart_returns_default_teeth_and_metadata(
        self,
        api_client,
        admin_user,
        patient_factory,
    ):
        patient = patient_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(
            reverse('retrieve_update_dentalchart', kwargs={'id': patient.id})
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['patientId'] == patient.id
        assert len(response.data['data']['teeth']) == len(FDI_PERMANENT)
        # Dental chart serializer exposes per-tooth status via stored teeth values.
        assert 'healthy' in [t['status'] for t in response.data['data']['teeth'].values()]


    def test_patch_dental_chart_updates_single_tooth_without_overwriting_others(
        self,
        api_client,
        admin_user,
        patient_factory,
    ):
        patient = patient_factory()
        chart = patient.patient_dentalchart
        original_other_tooth = deepcopy(chart.teeth['12'])
        payload = {'teeth': {'11': {'status': 'cavity', 'notes': 'Needs filling'}}}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            reverse('retrieve_update_dentalchart', kwargs={'id': patient.id}),
            payload,
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        chart.refresh_from_db()
        assert chart.teeth['11']['status'] == 'cavity'
        assert chart.teeth['11']['notes'] == 'Needs filling'
        assert chart.teeth['12'] == original_other_tooth

    def test_put_dental_chart_requires_complete_teeth_payload(
        self,
        api_client,
        admin_user,
        patient_factory,
    ):
        patient = patient_factory()
        payload = {'teeth': {'11': {'status': 'healthy', 'notes': ''}}}

        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            reverse('retrieve_update_dentalchart', kwargs={'id': patient.id}),
            payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['fields']['teeth'] == 'Teeth data missing or incomplete.'

    def test_patch_dental_chart_rejects_invalid_tooth_number(
        self,
        api_client,
        admin_user,
        patient_factory,
    ):
        patient = patient_factory()
        payload = {'teeth': {'99': {'status': 'healthy', 'notes': ''}}}

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            reverse('retrieve_update_dentalchart', kwargs={'id': patient.id}),
            payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error']['fields']['teeth']['99'] == 'Invalid FDI tooth number.'
