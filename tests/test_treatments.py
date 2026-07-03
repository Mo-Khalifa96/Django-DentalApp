import uuid
import pytest
from decimal import Decimal
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from patients.models import TreatmentPlan, TreatmentPlanItem


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _list_url(patient_id):
    return reverse('list_create_treatments', kwargs={'id': patient_id})

def _detail_url(patient_id, treatment_id):
    return reverse(
        'retrieve_update_delete_treatment',
        kwargs={'id': patient_id, 'treatmentId': treatment_id},
    )

def _lookup_url(treatment_id):
    return reverse('lookup_single_treatmentplan', kwargs={'id': treatment_id})

def _create_payload(*items, **overrides):
    """items: list of (procedure, price, **item_overrides) tuples, or use defaults."""
    if not items:
        raise ValueError("At least one item required")

    built_items = []
    total = Decimal('0')
    for entry in items:
        procedure, price = entry[0], entry[1]
        item_overrides = entry[2] if len(entry) > 2 else {}
        item = {
            'procedureId': procedure.id,
            'toothNumber': '11',
            'price':       str(price),
            'session':     1,
        }
        item.update(item_overrides)
        built_items.append(item)
        total += Decimal(str(price))

    base = {
        'title':     'Test Treatment Plan',
        'currency':  '$',
        'totalCost': str(total),
        'items':     built_items,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /patients/<id>/treatment-plans/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateTreatmentPlansAPIView:

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_lists_patient_treatment_plans(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient  = patient_factory(doctor=dentist_user)
        proc     = procedure_factory()
        plan     = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)
        other_p  = patient_factory(doctor=dentist_user)
        treatment_plan_factory(patient=other_p, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert [i['id'] for i in response.data['data']] == [str(plan.id)]

    def test_list_for_nonexistent_patient_returns_404(self, api_client, admin_user):
        """get_queryset() explicitly raises NotFound for a missing patient."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_plans_of_deleted_patients_excluded(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        """TreatmentPlansManager filters patient__is_deleted=False."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        patient.is_deleted = True
        patient.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id))
        # Patient itself is "not found" once soft-deleted, since get_queryset()
        # looks the patient up via Patient.objects (filtered manager)
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_assistant_cannot_list_treatment_plans(
        self, api_client, assistant_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(_list_url(patient.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_list_treatment_plans(self, api_client, patient_factory):
        patient = patient_factory()
        response = api_client.get(_list_url(patient.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_create_treatment_plan_calculates_total_cost(
        self, api_client, dentist_user, patient_factory, procedure_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc1   = procedure_factory(name='Exam')
        proc2   = procedure_factory(name='Filling')

        payload = _create_payload(
            (proc1, '100.00'),
            (proc2, '250.00', {'toothNumber': '12', 'session': 2}),
            installmentMonths=3,
            sessions=2,
        )
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(_list_url(patient.id), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert str(plan.totalCost) == '350.00'
        assert plan.treatment_items.count() == 2

    def test_create_recalculates_total_cost_when_client_value_is_wrong(
        self, api_client, dentist_user, patient_factory, procedure_factory
    ):
        """validate(): totalCost mismatch is logged but the correct sum is stored anyway."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()

        payload = _create_payload((proc, '100.00'), totalCost='999.00')
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(_list_url(patient.id), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert str(plan.totalCost) == '100.00'   # recalculated, not 999.00

    def test_create_sets_status_to_active_by_default(
        self, api_client, dentist_user, patient_factory, procedure_factory
    ):
        """TreatmentPlan.save(): status defaults to 'active'."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload((proc, '100.00')), format='json'
        )
        plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert plan.status == TreatmentPlan.TreatmentStatusChoices.ACTIVE

    def test_dentist_creating_plan_is_auto_assigned_as_doctor(
        self, api_client, dentist_user, patient_factory, procedure_factory
    ):
        """CreateTreatmentPlanSerializer.create(): dentist role → doctor = request.user."""
        patient = patient_factory(doctor=None)
        proc    = procedure_factory()
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload((proc, '100.00')), format='json'
        )
        plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert plan.doctor == dentist_user
        assert plan.doctorName == dentist_user.name

    def test_admin_creating_plan_falls_back_to_patients_doctor(
        self, api_client, admin_user, dentist_user, patient_factory, procedure_factory
    ):
        """
        TreatmentPlan.save(): when admin creates a plan (doctor not explicitly
        assigned by the serializer, since only 'dentist' role auto-assigns),
        the model's save() falls back to patient.doctor if set.
        """
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload((proc, '100.00')), format='json'
        )
        plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert plan.doctor == dentist_user

    def test_create_with_empty_items_returns_400(
        self, api_client, dentist_user, patient_factory
    ):
        """items is required, allow_empty=False."""
        patient = patient_factory(doctor=dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id),
            {'title': 'Empty Plan', 'totalCost': '0.00', 'items': []},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_invalid_procedure_id_returns_400(
        self, api_client, dentist_user, patient_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        api_client.force_authenticate(user=dentist_user)
        payload = {
            'title': 'Bad Plan',
            'totalCost': '100.00',
            'items': [{'procedureId': str(uuid.uuid4()), 'price': '100.00'}],
        }
        response = api_client.post(_list_url(patient.id), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_item_procedure_name_snapshot_set_on_create(
        self, api_client, dentist_user, patient_factory, procedure_factory
    ):
        """create(): TreatmentPlanItem.procedureName captured from the FK."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory(name='Root Canal')
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload((proc, '300.00')), format='json'
        )
        plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert plan.treatment_items.first().procedureName == 'Root Canal'

    def test_item_status_defaults_to_pending(
        self, api_client, dentist_user, patient_factory, procedure_factory
    ):
        """TreatmentPlanItem.save(): status defaults to 'pending'."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload((proc, '100.00')), format='json'
        )
        plan = TreatmentPlan.objects.get(id=response.data['data']['id'])
        assert plan.treatment_items.first().status == TreatmentPlanItem.ItemStatusChoices.PENDING

    def test_assistant_cannot_create_treatment_plan(
        self, api_client, assistant_user, patient_factory, procedure_factory
    ):
        patient = patient_factory()
        proc    = procedure_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload((proc, '100.00')), format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_create_response_is_wrapped(
        self, api_client, dentist_user, patient_factory, procedure_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload((proc, '100.00')), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | DELETE  /patients/<id>/treatment-plans/<treatmentId>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteTreatmentPlanAPIView:

    # ── routing ───────────────────────────────────────────────────────────────

    def test_patch_method_not_allowed(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        """PATCH excluded from http_method_names → 405."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(patient.id, plan.id), {'title': 'New'}, format='json'
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED or render_error(response)

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_treatment_plan(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(patient.id, plan.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['patientId'] == patient.id

    def test_other_dentist_cannot_retrieve_plan(
        self, api_client, dentist_user, other_dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=other_dentist_user)
        response = api_client.get(_detail_url(patient.id, plan.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_treatment_plan_for_wrong_patient_returns_404(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        """get_object(): filters by both patient_id AND treatmentId; mismatch → 404."""
        patient_a = patient_factory(doctor=dentist_user)
        patient_b = patient_factory(doctor=dentist_user)
        proc      = procedure_factory()
        plan      = treatment_plan_factory(patient=patient_a, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        # plan belongs to patient_a but we look it up under patient_b's URL
        response = api_client.get(_detail_url(patient_b.id, plan.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    # ── UPDATE (PUT) ──────────────────────────────────────────────────────────

    def test_admin_can_update_treatment_plan_title_and_items(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory(name='Cleaning')
        new_proc = procedure_factory(name='Implant')
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _detail_url(patient.id, plan.id),
            {
                'title': 'Updated Plan',
                'items': [{
                    'procedureId': new_proc.id,
                    'toothNumber': '21',
                    'price': '500.00',
                    'session': 1,
                    'status': 'completed',
                }],
            },
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        plan.refresh_from_db()
        assert plan.title == 'Updated Plan'
        assert str(plan.totalCost) == '500.00'
        assert plan.treatment_items.count() == 1
        assert plan.treatment_items.first().status == 'completed'

    def test_update_items_replaces_all_existing(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        """update(): 'items' present → delete + recreate."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)
        assert plan.treatment_items.count() == 1

        new_proc = procedure_factory(name='New Item')
        api_client.force_authenticate(user=admin_user)
        api_client.put(
            _detail_url(patient.id, plan.id),
            {'items': [
                {'procedureId': new_proc.id, 'price': '80.00', 'session': 1},
                {'procedureId': new_proc.id, 'price': '20.00', 'session': 2},
            ]},
            format='json',
        )
        plan.refresh_from_db()
        assert plan.treatment_items.count() == 2

    def test_update_without_items_key_preserves_existing(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        """update(): omitting 'items' leaves existing items untouched."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        api_client.put(
            _detail_url(patient.id, plan.id), {'title': 'Just rename'}, format='json'
        )
        plan.refresh_from_db()
        assert plan.treatment_items.count() == 1   # untouched

    def test_other_dentist_cannot_update_plan(
        self, api_client, dentist_user, other_dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)
        first_item = plan.treatment_items.first()

        api_client.force_authenticate(user=other_dentist_user)
        response = api_client.put(
            _detail_url(patient.id, plan.id),
            {
                'title': plan.title,
                'status': 'active',
                'items': [{
                    'procedureId': first_item.procedure_id,
                    'toothNumber': first_item.toothNumber,
                    'price': str(first_item.price),
                    'session': first_item.session,
                    'status': 'pending',
                }],
            },
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_update_response_is_wrapped(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _detail_url(patient.id, plan.id), {'title': 'Renamed'}, format='json'
        )
        assert response.data.get('success') is True
        assert 'data' in response.data

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_treatment_plan(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)
        pid     = plan.id

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_detail_url(patient.id, pid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not TreatmentPlan.objects.filter(id=pid).exists()

    def test_deleting_plan_cascades_to_items(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        """TreatmentPlanItem.treatmentPlan is on_delete=CASCADE."""
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)
        pid     = plan.id

        api_client.force_authenticate(user=admin_user)
        api_client.delete(_detail_url(patient.id, pid))

        assert not TreatmentPlanItem.objects.filter(treatmentPlan_id=pid).exists()

    def test_other_dentist_cannot_delete_plan(
        self, api_client, dentist_user, other_dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=other_dentist_user)
        response = api_client.delete(_detail_url(patient.id, plan.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_delete_plan(
        self, api_client, dentist_user, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)
        response = api_client.delete(_detail_url(patient.id, plan.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /treatment-plans/<id>/  (lookup independent of patient)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLookupTreatmentPlanAPIView:

    def test_admin_can_lookup_plan_directly(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_lookup_url(plan.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['id'] == str(plan.id)

    def test_other_dentist_cannot_lookup_plan(
        self, api_client, dentist_user, other_dentist_user, patient_factory,
        procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)

        api_client.force_authenticate(user=other_dentist_user)
        response = api_client.get(_lookup_url(plan.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_lookup_nonexistent_plan_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_lookup_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_unauthenticated_returns_401(
        self, api_client, dentist_user, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        proc    = procedure_factory()
        plan    = treatment_plan_factory(patient=patient, procedure=proc, doctor=dentist_user)
        response = api_client.get(_lookup_url(plan.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /treatment-plans/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveTreatmentPlansOptionsAPIView:
    URL = 'treatment_plans_options'

    def test_authenticated_user_gets_options_payload(
        self, api_client, admin_user, procedure_factory
    ):
        proc = procedure_factory(name='Bridge')
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('installmentOptions', 'treatmentStatusChoices',
                    'procedureChoices', 'itemStatusChoices', 'validToothNumbers'):
            assert key in response.data, f"Missing key: {key}"
        assert {'procedureId': proc.id, 'name': proc.name} in response.data['procedureChoices']

    def test_installment_options_cover_all_choices(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['installmentOptions']}
        expected = {c.value for c in TreatmentPlan.InstallmentMonthsChoices}
        assert returned == expected

    def test_treatment_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['treatmentStatusChoices']}
        expected = {c.value for c in TreatmentPlan.TreatmentStatusChoices}
        assert returned == expected

    def test_item_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['itemStatusChoices']}
        expected = {c.value for c in TreatmentPlanItem.ItemStatusChoices}
        assert returned == expected

    def test_valid_tooth_numbers_non_empty(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert len(response.data['validToothNumbers']) > 0

    def test_procedure_choices_empty_when_branches_exist_and_no_branch_id(
        self, api_client, admin_user, branch_factory, procedure_factory
    ):
        b = branch_factory()
        procedure_factory(branch=b)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['procedureChoices'] == []

    def test_procedure_choices_filtered_by_branch_id(
        self, api_client, admin_user, branch_factory, procedure_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        proc_b1 = procedure_factory(branch=b1)
        proc_b2 = procedure_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        procedure_names = {c['procedureId'] for c in response.data['procedureChoices']}
        assert proc_b1.id in procedure_names
        assert proc_b2.id not in procedure_names

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)