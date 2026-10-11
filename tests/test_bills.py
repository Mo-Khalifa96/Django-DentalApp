import uuid
import pytest
from decimal import Decimal
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from finances.models import Bill


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bill_url(bill_id):
    return reverse('retrieve_update_delete_bill', kwargs={'id': bill_id})

def _invoice_url(bill_id):
    return reverse('autogenerate_invoice', kwargs={'id': bill_id})

def _list_item(api_client, bill):
    response = api_client.get(reverse('list_create_bills'))
    return next(b for b in response.data['data'] if b['id'] == str(bill.id))


# ─────────────────────────────────────────────────────────────────────────────
# Create payload helper
# ─────────────────────────────────────────────────────────────────────────────

def _create_payload(patient, visit, **overrides):
    base = {
        'patientId':   str(patient.id),
        'visitIds':    [str(visit.id)],
        'description': 'Test Bill',
        'subtotal':    '200.00',
        'discount':    '0.00',
        'currency':    '$',
        'branchId':    None,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /bills/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateBillsAPIView:
    LIST_URL = 'list_create_bills'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_bills(
        self, api_client, admin_user, bill_factory
    ):
        b1 = bill_factory()
        b2 = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(b['id']) for b in response.data['data']]
        assert str(b1.id) in ids
        assert str(b2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, bill_factory
    ):
        bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"

    def test_admin_list_includes_soft_deleted_bills(
        self, api_client, admin_user, bill_factory
    ):
        """Admin uses Bill.all_objects so soft-deleted bills still appear."""
        bill = bill_factory()
        bill.isDeleted = True
        bill.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(bill.id) in [str(b['id']) for b in response.data['data']]

    def test_soft_deleted_bills_hidden_from_non_admin(
        self, api_client, user_factory, bill_factory, branch_factory
    ):
        """Bill.objects filters isDeleted=False; non-admins cannot see soft-deleted bills."""
        b = branch_factory()
        user = user_factory(role='accountant')
        user.branches.set([b])

        bill = bill_factory(branch=b)
        bill.isDeleted = True
        bill.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(bill.id) not in [str(b['id']) for b in response.data['data']]

    def test_dentist_sees_only_own_patients_bills(
        self, api_client, dentist_user, other_dentist_user, patient_factory,
        visit_factory, bill_factory
    ):
        """GET queryset: dentist path → filter(patient__doctor=user)."""
        p_own = patient_factory(doctor=dentist_user)
        p_other = patient_factory(doctor=other_dentist_user)
        v_own = visit_factory(patient=p_own, doctor=dentist_user)
        v_other = visit_factory(patient=p_other, doctor=other_dentist_user)

        bill_own = bill_factory(patient=p_own, visits=[v_own])
        bill_other = bill_factory(patient=p_other, visits=[v_other])

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [str(b['id']) for b in response.data['data']]
        assert str(bill_own.id) in ids
        assert str(bill_other.id) not in ids

    def test_list_response_includes_status_annotation(
        self, api_client, admin_user, bill_factory
    ):
        """Status is computed via Case/When annotation; must appear in response."""
        bill_factory(totalAmount=Decimal('200.00'), totalPaid=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        item = response.data['data'][0]
        assert 'status' in item
        assert item['status'] is not None   #unpaid' when totalPaid is null

    def test_user_without_view_bills_permission_gets_403(
        self, api_client, assistant_user
    ):
        """receptionist default permissions do not include 'view.bills'."""
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_bill(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Bill.objects.filter(patient=patient).exists()

    def test_create_auto_sets_snapshot_fields(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory, branch
    ):
        """save(): patientName and branchName captured from FKs on creation."""
        patient = patient_factory(name='Snapshot Patient')
        visit = visit_factory(patient=patient, doctor=dentist_user)
        admin_user.branch = branch
        admin_user.branches.add(branch)
        admin_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit, branchId=str(branch.id)),
            format='json',
        )
        bill = Bill.objects.get(patient=patient)
        assert bill.patientName == 'Snapshot Patient'
        assert bill.branchName == branch.name

    def test_create_sets_created_by_from_request_user(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """validate() assigns createdBy = request.user.name."""
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(patient, visit), format='json'
        )
        bill = Bill.objects.get(patient=patient)
        assert bill.createdBy == admin_user.name

    def test_create_calculates_total_from_subtotal_minus_discount(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """validate() recalculates totalAmount = subtotal − discount regardless of client input."""
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit, subtotal='200.00', discount='50.00'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        bill = Bill.objects.get(patient=patient)
        assert bill.totalAmount == Decimal('150.00')

    def test_create_with_discount_exceeding_subtotal_returns_400(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit, subtotal='100.00', discount='150.00'),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_visit_belonging_to_wrong_patient_returns_400(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """validate(): all visits must belong to the same patient as the bill."""
        patient_a = patient_factory()
        patient_b = patient_factory()
        visit_b = visit_factory(patient=patient_b, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient_a, visit_b),   #isit belongs to patient_b, not patient_a
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_without_branch_id_returns_400(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """branchId is now required=True; omitting it entirely → 400."""
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        payload = {
            'patientId':   str(patient.id),
            'visitIds':    [str(visit.id)],
            'description': 'No Branch Bill',
            'subtotal':    '200.00',
            'currency':    '$',
            #ranchId key absent
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_m2m_signal_updates_visit_cost_after_bill_created(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """
        m2m_changed signal: post_add on Bill.visits recalculates visit.cost as
        Sum(totalAmount) across all bills for that visit.
        """
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        initial_cost = visit.cost

        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit, subtotal='350.00'),
            format='json',
        )
        visit.refresh_from_db()
        # Signal sets cost = totalAmount of the new bill (350 - 0 = 350)
        assert visit.cost != initial_cost
        assert visit.cost == Decimal('350.00')

    def test_user_with_create_bill_permission_can_create(
        self, api_client, receptionist_user, patient_factory, dentist_user, visit_factory
    ):
        """receptionist has 'create.bill' by default."""
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_response_is_wrapped(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        patient = patient_factory()
        visit = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient, visit), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data


# ══════════════════════════════════════════════════════════════════════════════
# POST /bills/ — visits optional, treatment rules, installment conflict
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCreateBillRules:
    URL = 'list_create_bills'

    @staticmethod
    def _treatment_payload(patient, treatment, **overrides):
        base = {
            'patientId': str(patient.id), 'treatmentId': str(treatment.id),
            'description': 'Treatment bill', 'subtotal': '100.00', 'discount': '0.00',
            'currency': '$', 'branchId': None,
        }
        base.update(overrides)
        return base

    @pytest.mark.parametrize('visit_ids', ['omitted', []])
    def test_visit_ids_are_optional(
        self, api_client, admin_user, patient_factory, visit_factory, dentist_user, visit_ids
    ):
        patient = patient_factory()
        payload = _create_payload(patient, visit_factory(patient=patient, doctor=dentist_user))
        if visit_ids == 'omitted':
            payload.pop('visitIds')
        else:
            payload['visitIds'] = visit_ids

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Bill.objects.get(patient=patient).visits.count() == 0

    def test_null_visit_ids_is_accepted(
        self, api_client, admin_user, patient_factory, visit_factory, dentist_user
    ):
        """
        Expected to FAIL with 400 "may not be null": DRF doesn't forward allow_null to the list-level
        field of a many=True relation. If it fails, drop allow_null from visitIds on CreateBillSerializer
        and tell the frontend to send [] or omit the key.
        """
        patient = patient_factory()
        payload = _create_payload(patient, visit_factory(patient=patient, doctor=dentist_user), visitIds=None)

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.URL), payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_bill_for_patients_treatment(
        self, api_client, admin_user, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory()
        treatment = treatment_plan_factory(patient=patient, procedure=procedure_factory())

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.URL), self._treatment_payload(patient, treatment), format='json')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        bill = Bill.objects.get(patient=patient)
        assert bill.treatment == treatment
        assert bill.treatmentTitle == treatment.title

    def test_treatment_of_another_patient_returns_400(
        self, api_client, admin_user, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient, other = patient_factory(), patient_factory()
        treatment = treatment_plan_factory(patient=other, procedure=procedure_factory())

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.URL), self._treatment_payload(patient, treatment), format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'treatmentId' in response.data['error']['fields']

    def test_subtotal_above_treatment_cost_returns_400(
        self, api_client, admin_user, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory()
        treatment = treatment_plan_factory(patient=patient, procedure=procedure_factory())   # totalCost 120.00

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._treatment_payload(patient, treatment, subtotal='500.00'), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'treatmentId' in response.data['error']['fields']

    def test_bill_for_treatment_with_installment_bill_returns_409_with_bill_id(
        self, api_client, admin_user, installment_plan_factory, plan_bill_factory
    ):
        plan = installment_plan_factory()
        existing = plan_bill_factory(plan)
        patient = plan.treatment.patient

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._treatment_payload(patient, plan.treatment), format='json'
        )

        assert response.status_code == status.HTTP_409_CONFLICT or render_error(response)
        render_error(response)
        error = response.data['error']
        assert error['code'] == 'INSTALLMENT_BILL_ALREADY_EXISTS'
        assert str(error['message']) == 'An installment bill already exists for this treatment plan.'
        assert str(error['billId']) == str(existing.id)
        assert Bill.objects.filter(treatment=plan.treatment).count() == 1

    def test_bill_for_treatment_whose_plan_has_no_bill_is_allowed_as_plain_bill(
        self, api_client, admin_user, installment_plan_factory
    ):
        plan = installment_plan_factory()
        patient = plan.treatment.patient

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._treatment_payload(patient, plan.treatment), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Bill.objects.get(patient=patient).installmentPlan is None


# ══════════════════════════════════════════════════════════════════════════════
# GET | PATCH | PUT | DELETE  /bills/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteBillAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_bill(
        self, api_client, admin_user, bill_factory
    ):
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_bill_url(bill.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['id'] == str(bill.id)

    def test_retrieve_response_includes_metadata(
        self, api_client, admin_user, bill_factory
    ):
        """RetrieveBillSerializer inherits UserPermissionsMixin → metadata on GET."""
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_bill_url(bill.id))

        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_admin_sees_extra_snapshot_fields(
        self, api_client, admin_user, bill_factory
    ):
        """BillSerializer.get_fields(): admin response includes treatmentTitle, createdBy, etc."""
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_bill_url(bill.id))

        data = response.data['data']
        for field in ('branchName', 'createdBy', 'isDeleted'):
            assert field in data, f"Admin should see '{field}'"

    def test_non_admin_does_not_see_snapshot_fields(
        self, api_client, user_factory, bill_factory, branch_factory
    ):
        """BillSerializer.get_fields() strips snapshot fields for non-admins."""
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        bill = bill_factory(branch=b)

        api_client.force_authenticate(user=accountant)
        response = api_client.get(_bill_url(bill.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        data = response.data['data']
        for field in ('branchName', 'createdBy', 'isDeleted', 'treatmentTitle', 'procedures'):
            assert field not in data, f"Non-admin should NOT see '{field}'"

    def test_admin_can_retrieve_soft_deleted_bill(
        self, api_client, admin_user, bill_factory
    ):
        """Admin's get_queryset uses Bill.all_objects; soft-deleted bills are visible."""
        bill = bill_factory()
        bill.isDeleted = True
        bill.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_bill_url(bill.id))
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_non_admin_cannot_retrieve_soft_deleted_bill(
        self, api_client, user_factory, bill_factory, branch_factory
    ):
        """Non-admin's get_queryset uses Bill.objects (isDeleted=False) → 404."""
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        bill = bill_factory(branch=b)
        bill.isDeleted = True
        bill.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=accountant)
        response = api_client.get(_bill_url(bill.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    # ── UPDATE ────────────────────────────────────────────────────────────────

    def test_admin_can_update_bill_description(
        self, api_client, admin_user, bill_factory
    ):
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _bill_url(bill.id), {'description': 'Updated Description'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        bill.refresh_from_db()
        assert bill.description == 'Updated Description'

    def test_update_recalculates_total_when_subtotal_changes(
        self, api_client, admin_user, bill_factory
    ):
        """UpdateBillSerializer.validate() recalculates totalAmount on update."""
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _bill_url(bill.id),
            {'subtotal': '300.00', 'discount': '50.00'},
            format='json',
        )
        bill.refresh_from_db()
        assert bill.totalAmount == Decimal('250.00')

    def test_branch_is_read_only_on_update(
        self, api_client, admin_user, bill_factory, branch_factory
    ):
        """UpdateBillSerializer: branchId is in read_only_fields."""
        original_branch = branch_factory()
        new_branch = branch_factory()
        bill = bill_factory(branch=original_branch)

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _bill_url(bill.id), {'branchId': str(new_branch.id)}, format='json'
        )
        bill.refresh_from_db()
        assert bill.branch == original_branch

    def test_visits_signal_update_triggers_signal_and_calculates_missing_costs(
        self, api_client, admin_user, bill_factory, patient_factory, dentist_user,
        visit_factory
    ):
        """
        UpdateBillSerializer.update(): visits.set() replaces M2M and fires the
        m2m_changed signal, recalculating cost for affected visits. 
        """
        patient = patient_factory()
        v1 = visit_factory(patient=patient, doctor=dentist_user)
        v2 = visit_factory(patient=patient, doctor=dentist_user)
        bill = bill_factory(patient=patient, visits=[v1],
            subtotal=Decimal('200.00'), totalAmount=Decimal('200.00'))

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(_bill_url(bill.id), {'visitIds': [str(v2.id)]}, format='json')

        assert response.status_code == status.HTTP_200_OK or render_error(response)

        #Signal should have updated v2.cost but not v1.cost
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v2 in bill.visits.all()
        assert v2.cost == Decimal('200.00')
        assert v1.cost == Decimal('200.00')

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_hard_deletes_bill(
        self, api_client, admin_user, bill_factory
    ):
        """BillManager.delete_bill: admin → permanent delete."""
        bill = bill_factory()
        bid = bill.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_bill_url(bid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not Bill.objects.filter(id=bid).exists()
        assert not Bill.all_objects.filter(id=bid).exists()

    def test_non_admin_with_delete_permission_soft_deletes_bill(
        self, api_client, user_factory, bill_factory, branch_factory
    ):
        """BillManager.delete_bill: non-admin → isDeleted=True, still in all_objects."""
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        bill = bill_factory(branch=b)
        bid = bill.id

        api_client.force_authenticate(user=accountant)
        response = api_client.delete(_bill_url(bid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not Bill.objects.filter(id=bid).exists()
        deleted = Bill.all_objects.get(id=bid)
        assert deleted.isDeleted is True

    def test_unauthenticated_cannot_delete(self, api_client, bill_factory):
        bill = bill_factory()
        response = api_client.delete(_bill_url(bill.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET /bills/ — payment progress, installment flags, credit-held flag
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBillPaymentFields:

    def test_status_follows_payment_progress(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        unpaid = bill_factory(totalAmount=Decimal('200.00'), subtotal=Decimal('200.00'))
        partial = bill_factory(totalAmount=Decimal('200.00'), subtotal=Decimal('200.00'))
        paid = bill_factory(totalAmount=Decimal('200.00'), subtotal=Decimal('200.00'))
        transaction_factory(bill=partial, amount=Decimal('100.00'))
        transaction_factory(bill=paid, amount=Decimal('200.00'))

        api_client.force_authenticate(user=admin_user)
        assert str(_list_item(api_client, unpaid)['status']).lower() == 'unpaid'
        assert str(_list_item(api_client, partial)['status']).lower() == 'partial'
        assert str(_list_item(api_client, paid)['status']).lower() == 'paid'

    def test_collected_split_between_patient_and_insurer(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        bill = bill_factory(totalAmount=Decimal('300.00'), subtotal=Decimal('300.00'))
        transaction_factory(bill=bill, amount=Decimal('100.00'), method='cash')
        transaction_factory(bill=bill, amount=Decimal('60.00'), method='insurance')

        api_client.force_authenticate(user=admin_user)
        item = _list_item(api_client, bill)

        assert Decimal(item['collectedFromPatient']) == Decimal('100.00')
        assert Decimal(item['collectedFromInsurer']) == Decimal('60.00')
        assert Decimal(item['totalPaid']) == Decimal('160.00')

    def test_refunded_transaction_leaves_both_collected_figures_and_total_paid(
        self, api_client, admin_user, bill_factory, transaction_factory, refund_transaction
    ):
        bill = bill_factory(totalAmount=Decimal('300.00'), subtotal=Decimal('300.00'))
        cash = transaction_factory(bill=bill, amount=Decimal('100.00'), method='cash')
        transaction_factory(bill=bill, amount=Decimal('60.00'), method='insurance')
        refund_transaction(transaction=cash)

        api_client.force_authenticate(user=admin_user)
        item = _list_item(api_client, bill)

        assert Decimal(item['collectedFromPatient']) == Decimal('0.00')
        assert Decimal(item['collectedFromInsurer']) == Decimal('60.00')
        assert Decimal(item['totalPaid']) == Decimal('60.00')   # partial refund: only the refunded part leaves

    def test_installment_flags_in_list_and_retrieve(
        self, api_client, admin_user, installment_plan_factory, plan_bill_factory, bill_factory
    ):
        plan = installment_plan_factory()
        plan_bill = plan_bill_factory(plan)
        plain_bill = bill_factory()
        api_client.force_authenticate(user=admin_user)

        linked = _list_item(api_client, plan_bill)
        assert linked['hasInstallmentPlan'] is True
        assert str(linked['installmentPlanId']) == str(plan.id)

        plain = _list_item(api_client, plain_bill)
        assert plain['hasInstallmentPlan'] is False
        assert plain['installmentPlanId'] is None

        detail = api_client.get(_bill_url(plan_bill.id)).data['data']
        assert detail['hasInstallmentPlan'] is True

    def test_non_admin_still_sees_payment_progress_fields(
        self, api_client, user_factory, bill_factory, branch_factory
    ):
        """Snapshot fields are stripped for non-admins; payment-progress and flag fields are not.
        Drop 'isCreditHeld' from the list if you made it admin-only."""
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        bill = bill_factory(branch=b)

        api_client.force_authenticate(user=accountant)
        data = api_client.get(_bill_url(bill.id)).data['data']
        for field in ('totalPaid', 'collectedFromPatient', 'collectedFromInsurer',
                      'installmentPlanId', 'hasInstallmentPlan', 'isCreditHeld'):
            assert field in data, f"Non-admin should see '{field}'"


# ══════════════════════════════════════════════════════════════════════════════
# Installment-plan bills
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInstallmentPlanBills:

    @pytest.mark.parametrize('method', ['put', 'patch'])
    def test_plan_bill_is_not_editable_through_bills_endpoint(
        self, api_client, admin_user, installment_plan_factory, plan_bill_factory, method
    ):
        bill = plan_bill_factory(installment_plan_factory())
        api_client.force_authenticate(user=admin_user)
        response = getattr(api_client, method)(_bill_url(bill.id), {'description': 'tampered'}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_plan_bill_can_be_deleted_and_the_plan_survives(
        self, api_client, admin_user, installment_plan_factory, plan_bill_factory
    ):
        from finances.models import InstallmentPlan
        plan = installment_plan_factory()
        bill = plan_bill_factory(plan)
        api_client.force_authenticate(user=admin_user)

        response = api_client.delete(_bill_url(bill.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert InstallmentPlan.objects.filter(id=plan.id).exists()   # FK cascade runs plan -> bill, not back
        assert plan.active_bill is None


# ══════════════════════════════════════════════════════════════════════════════
# Deposit bills (isDepositBill / isCreditHeld)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDepositBills:

    def test_held_deposit_bill_is_listed_as_paid_and_credit_held(
        self, api_client, admin_user, deposit_factory
    ):
        deposit = deposit_factory(amount=Decimal('500.00'))
        api_client.force_authenticate(user=admin_user)
        item = _list_item(api_client, deposit.bill)

        assert item['isCreditHeld'] is True
        assert str(item['status']).lower() == 'paid'
        assert Decimal(item['collectedFromPatient']) == Decimal('500.00')

    def test_deposit_bill_is_visible_to_branch_staff(
        self, api_client, user_factory, branch_factory, patient_factory, procedure_factory,
        treatment_plan_factory, deposit_factory
    ):
        b = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b])
        patient = patient_factory(branch=b)
        treatment = treatment_plan_factory(patient=patient, procedure=procedure_factory())
        deposit = deposit_factory(treatment=treatment)

        api_client.force_authenticate(user=accountant)
        assert _list_item(api_client, deposit.bill)['isCreditHeld'] is True

    def test_refund_clears_credit_flag_but_keeps_deposit_flag_and_amounts(
        self, api_client, admin_user, deposit_factory, refund_transaction
    ):
        deposit = deposit_factory(amount=Decimal('500.00'))
        bill = deposit.bill
        api_client.force_authenticate(user=admin_user)

        refund_transaction(transaction=deposit)

        bill.refresh_from_db()
        assert bill.isCreditHeld is False
        assert bill.isDepositBill is True                  # permanent: keeps it out of 'billed' analytics
        assert bill.totalPaid == Decimal('500.00')         # deliberately not zeroed (frontend note)
        assert 'Refunded' in bill.description
        item = _list_item(api_client, bill)
        assert item['isCreditHeld'] is False
        assert Decimal(item['collectedFromPatient']) == Decimal('0.00')

    def test_reversing_a_refund_restores_the_hold(self, deposit_factory, refund_transaction):
        deposit = deposit_factory(amount=Decimal('500.00'))
        bill = deposit.bill
        original_description = bill.description

        refund_transaction(transaction=deposit)
        deposit.refresh_from_db()
        deposit.status = 'completed'
        deposit.save()

        bill.refresh_from_db()
        assert bill.isCreditHeld is True
        assert bill.description == original_description

    @pytest.mark.parametrize('method', ['put', 'patch'])
    def test_held_deposit_bill_is_not_editable(self, api_client, admin_user, deposit_factory, method):
        bill = deposit_factory().bill
        api_client.force_authenticate(user=admin_user)
        response = getattr(api_client, method)(_bill_url(bill.id), {'description': 'tampered'}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_refunded_deposit_bill_is_still_not_editable(
        self, api_client, admin_user, deposit_factory, refund_transaction
    ):
        """Fails if the exclusion is keyed on isCreditHeld instead of isDepositBill (see section 3)."""
        deposit = deposit_factory()
        refund_transaction(transaction=deposit)
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(_bill_url(deposit.bill.id), {'description': 'tampered'}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_held_deposit_bill_cannot_be_deleted(self, api_client, admin_user, deposit_factory):
        deposit = deposit_factory()
        bill = deposit.bill
        api_client.force_authenticate(user=admin_user)

        response = api_client.delete(_bill_url(bill.id))

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert Bill.all_objects.filter(id=bill.id).exists()
        deposit.refresh_from_db()
        assert deposit.bill_id == bill.id

    def test_invoice_can_be_generated_for_a_deposit_bill(self, api_client, admin_user, deposit_factory):
        """Deliberate decision: a printable receipt for money received is a legitimate invoice."""
        from finances.models import Invoice
        bill = deposit_factory().bill
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(_invoice_url(bill.id), {'billId': str(bill.id)}, format='json')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Invoice.objects.filter(bill=bill).exists()



# ══════════════════════════════════════════════════════════════════════════════
# POST  /bills/<id>/generate-invoice/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAutogenerateInvoiceAPIView:

    def test_admin_can_autogenerate_invoice(self, api_client, admin_user, bill_factory):
        from finances.models import Invoice
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _invoice_url(bill.id),
            {'billId': str(bill.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Invoice.objects.filter(bill=bill).exists()

    def test_user_with_create_invoice_permission_can_generate(
        self, api_client, user_factory, bill_factory, branch_factory
    ):
        """receptionist has 'create.invoice' by default."""
        b = branch_factory()
        receptionist = user_factory(role='receptionist')
        receptionist.branches.set([b])
        bill = bill_factory(branch=b)

        api_client.force_authenticate(user=receptionist)
        response = api_client.post(
            _invoice_url(bill.id),
            {'billId': str(bill.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_generate_invoice_response_is_wrapped(
        self, api_client, admin_user, bill_factory
    ):
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _invoice_url(bill.id),
            {'billId': str(bill.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_unauthenticated_cannot_generate_invoice(
        self, api_client, bill_factory
    ):
        bill = bill_factory()
        response = api_client.post(
            _invoice_url(bill.id), {'billId': str(bill.id)}, format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /bills/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveBillsOptionsAPIView:
    """
    Plain generics.GenericAPIView + BranchToSerializerMixin.
    ResponseMixin NOT applied.
    """
    URL = 'bills_options'

    def test_authenticated_user_gets_options_payload(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'patientChoices',
                    'patientTreatmentChoices', 'patientVisitChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        assert 'success' not in api_client.get(reverse(self.URL)).data

    def test_patient_choices_filtered_by_branch_id(
        self, api_client, admin_user, patient_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        p1 = patient_factory(branch=b1)
        p2 = patient_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        patient_ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p1.id) in patient_ids
        assert str(p2.id) not in patient_ids

    def test_patient_choices_filtered_by_doctor_id(
        self, api_client, admin_user, patient_factory, dentist_user
    ):
        p_own = patient_factory(doctor=dentist_user)
        p_other = patient_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'doctorId': str(dentist_user.id)})

        patient_ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p_own.id) in patient_ids
        assert str(p_other.id) not in patient_ids

    def test_treatment_and_visit_choices_filtered_by_patient_id(
        self, api_client, admin_user, patient_factory, visit_factory, dentist_user,
        treatment_plan_factory, procedure_factory
    ):
        """patientTreatmentChoices and patientVisitChoices filtered when patientId is provided."""
        p1 = patient_factory()
        p2 = patient_factory()
        proc = procedure_factory()
        visit_p1 = visit_factory(patient=p1, doctor=dentist_user)
        treatment_plan_factory(patient=p1, procedure=proc)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'patientId': str(p1.id)})

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        visit_ids = {str(c['visitId']) for c in response.data['patientVisitChoices']}
        assert str(visit_p1.id) in visit_ids

    def test_invalid_patient_id_returns_400(self, api_client, admin_user):
        """BranchToSerializerMixin-level validation via get_serializer_context."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'patientId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)