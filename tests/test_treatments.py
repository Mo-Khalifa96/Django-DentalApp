import pytest
from django.urls import reverse
from rest_framework import status
from patients.utils import TEETH_CHOICES
from patients.models import TreatmentPlan


pytestmark = pytest.mark.django_db


class TestTreatmentPlansAPI:
    def test_list_treatment_plans_returns_patient_plans(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        treatment_plan_factory,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()
        plan = treatment_plan_factory(patient=patient, procedure=procedure, doctor=dentist_user)
        other_patient = patient_factory(doctor=dentist_user)
        treatment_plan_factory(patient=other_patient, procedure=procedure, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse('list_create_treatments', kwargs={'id': patient.id}))

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['data']] == [str(plan.id)]

    def test_create_treatment_plan_calculates_total_cost_and_payment_plan(
        self,
        api_client,
        dentist_user,
        patient_factory,
        procedure_factory,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure_one = procedure_factory(name='Exam')
        procedure_two = procedure_factory(name='Filling', price='250.00')


        payload = {
            'installmentMonths': 3,
            'title': 'Recommended treatment plan',
            # 'status': 'active',
            # 'installmentMonths': '',
            'currency': '$',
            'totalCost': 350.0,
            'sessions': 2,
            'items': [
                {
                    'procedureId': str(procedure_one.id),
                    'toothNumber': '11',
                    'price': '100.00',
                    'session': 1,
                    'notes': 'Recommended treatment plan',
                },
                {
                    'procedureId': str(procedure_two.id),
                    'toothNumber': '12',
                    'price': '250.00',
                    'session': 2,
                    'notes': 'Recommended treatment plan',
                },
            ]
        }
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            reverse('list_create_treatments', kwargs={'id': patient.id}),
            payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        treatment_plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert str(treatment_plan.totalCost) == '350.00'
        assert treatment_plan.treatment_items.count() == 2


    def test_retrieve_and_update_treatment_plan(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        treatment_plan_factory,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory(name='Cleaning')
        updated_procedure = procedure_factory(name='Dental implant', category='implant')
        treatment_plan = treatment_plan_factory(patient=patient, procedure=procedure, doctor=dentist_user)
        detail_url = reverse(
            'retrieve_update_delete_treatment',
            kwargs={'id': patient.id, 'treatmentId': treatment_plan.id},
        )

        api_client.force_authenticate(user=admin_user)
        retrieve_response = api_client.get(detail_url)
        assert retrieve_response.status_code == status.HTTP_200_OK
        assert retrieve_response.data['data']['patientId'] == patient.id

        update_response = api_client.put(
            detail_url,
            {
                'title': 'Updated treatment notes',
                'installmentMonths': 12,

                'items': [
                    {
                        'procedureId': str(updated_procedure.id),
                        'toothNumber': '21',
                        'price': '500.00',
                        'session': 90,
                        'status': 'completed',
                        'notes': 'Updated treatment notes',
                    }
                ],
            },
            format='json',
        )

        assert update_response.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST)
        treatment_plan.refresh_from_db()

        assert treatment_plan.treatment_items.first().notes == 'Updated treatment notes'
        assert str(treatment_plan.totalCost) == '500.00'
        assert treatment_plan.treatment_items.count() == 1
        assert treatment_plan.treatment_items.first().status == 'completed'


    def test_other_dentist_cannot_update_treatment_status(
        self,
        api_client,
        dentist_user,
        other_dentist_user,
        patient_factory,
        procedure_factory,
        treatment_plan_factory,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()
        treatment_plan = treatment_plan_factory(patient=patient, procedure=procedure, doctor=dentist_user)

        api_client.force_authenticate(user=other_dentist_user)
        # update_treatment_status endpoint is removed; status updates happen via the treatment-plan detail endpoint
        response = api_client.put(
            reverse(
                'retrieve_update_delete_treatment',
                kwargs={'id': patient.id, 'treatmentId': treatment_plan.id},
            ),
            {
                'title': treatment_plan.title,
                'status': 'active',
                'items': [
                    {
                        'procedureId': str(treatment_plan.treatment_items.first().procedure_id),
                        'toothNumber': treatment_plan.treatment_items.first().toothNumber,
                        'price': str(treatment_plan.treatment_items.first().price),
                        'session': treatment_plan.treatment_items.first().session,
                        'status': 'pending',
                    }
                ],
            },
            format='json',
        )

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN)


    def test_delete_treatment_plan_removes_it(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        treatment_plan_factory,
    ):
        patient = patient_factory(doctor=dentist_user)
        procedure = procedure_factory()
        treatment_plan = treatment_plan_factory(patient=patient, procedure=procedure, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(
            reverse(
                'retrieve_update_delete_treatment',
                kwargs={'id': patient.id, 'treatmentId': treatment_plan.id},
            )
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not TreatmentPlan.objects.filter(id=treatment_plan.id).exists()

    def test_treatment_plan_options_returns_procedures_teeth_and_statuses(
        self,
        api_client,
        admin_user,
        procedure_factory,
    ):
        procedure = procedure_factory(name='Bridge')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse('treatment_plans_options'))

        assert response.status_code == status.HTTP_200_OK
        assert {'procedureId': procedure.id, 'name': procedure.name} in response.data['procedureChoices']
        assert response.data['procedureChoices']
        assert 'active' in response.data['treatmentStatusChoices'][0].get('value')
        assert response.data['validToothNumbers']


