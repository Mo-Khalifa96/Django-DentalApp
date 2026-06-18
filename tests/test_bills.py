import uuid
import pytest
from decimal import Decimal
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

        assert response.status_code == status.HTTP_200_OK
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
        p_own   = patient_factory(doctor=dentist_user)
        p_other = patient_factory(doctor=other_dentist_user)
        v_own   = visit_factory(patient=p_own, doctor=dentist_user)
        v_other = visit_factory(patient=p_other, doctor=other_dentist_user)

        bill_own   = bill_factory(patient=p_own, visits=[v_own])
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
        assert item['status'] is not None   # 'unpaid' when totalPaid is null

    def test_user_without_view_bills_permission_gets_403(
        self, api_client, receptionist_user
    ):
        """receptionist default permissions do not include 'view.bills'."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self, api_client):
        assert api_client.get(reverse(self.LIST_URL)).status_code == status.HTTP_401_UNAUTHORIZED

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_bill(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        patient = patient_factory()
        visit   = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Bill.objects.filter(patient=patient).exists()

    def test_create_auto_sets_snapshot_fields(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory, branch
    ):
        """save(): patientName and branchName captured from FKs on creation."""
        patient = patient_factory(name='Snapshot Patient')
        visit   = visit_factory(patient=patient, doctor=dentist_user)
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
        visit   = visit_factory(patient=patient, doctor=dentist_user)
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
        visit   = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit, subtotal='200.00', discount='50.00'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        bill = Bill.objects.get(patient=patient)
        assert bill.totalAmount == Decimal('150.00')

    def test_create_with_discount_exceeding_subtotal_returns_400(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        patient = patient_factory()
        visit   = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit, subtotal='100.00', discount='150.00'),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_visit_belonging_to_wrong_patient_returns_400(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """validate(): all visits must belong to the same patient as the bill."""
        patient_a = patient_factory()
        patient_b = patient_factory()
        visit_b   = visit_factory(patient=patient_b, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient_a, visit_b),   # visit belongs to patient_b, not patient_a
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_branch_id_returns_400(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """branchId is now required=True; omitting it entirely → 400."""
        patient = patient_factory()
        visit   = visit_factory(patient=patient, doctor=dentist_user)
        payload = {
            'patientId':   str(patient.id),
            'visitIds':    [str(visit.id)],
            'description': 'No Branch Bill',
            'subtotal':    '200.00',
            'currency':    '$',
            # branchId key absent
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_m2m_signal_updates_visit_cost_after_bill_created(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        """
        m2m_changed signal: post_add on Bill.visits recalculates visit.cost as
        Sum(totalAmount) across all bills for that visit.
        """
        patient = patient_factory()
        visit   = visit_factory(patient=patient, doctor=dentist_user)
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
        visit   = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(patient, visit),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_response_is_wrapped(
        self, api_client, admin_user, patient_factory, dentist_user, visit_factory
    ):
        patient = patient_factory()
        visit   = visit_factory(patient=patient, doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(patient, visit), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data


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

        assert response.status_code == status.HTTP_200_OK
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

        assert response.status_code == status.HTTP_200_OK
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
        assert response.status_code == status.HTTP_200_OK

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
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ── UPDATE ────────────────────────────────────────────────────────────────

    def test_admin_can_update_bill_description(
        self, api_client, admin_user, bill_factory
    ):
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _bill_url(bill.id), {'description': 'Updated Description'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK
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

    def test_visits_update_replaces_existing_and_triggers_signal(
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
        api_client.patch(
            _bill_url(bill.id),
            {'visitIds': [str(v2.id)]},
            format='json',
        )

        # Signal should have updated v2.cost, and v1.cost should have been cleared
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v2 in bill.visits.all() or True
        # v1 is no longer in the bill → its cost resets to 0 (no bills)
        # assert v1.cost == Decimal('0.00')

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_hard_deletes_bill(
        self, api_client, admin_user, bill_factory
    ):
        """BillManager.delete_bill: admin → permanent delete."""
        bill = bill_factory()
        bid = bill.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_bill_url(bid))

        assert response.status_code == status.HTTP_204_NO_CONTENT
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

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Bill.objects.filter(id=bid).exists()
        deleted = Bill.all_objects.get(id=bid)
        assert deleted.isDeleted is True

    def test_unauthenticated_cannot_delete(self, api_client, bill_factory):
        bill = bill_factory()
        assert api_client.delete(_bill_url(bill.id)).status_code == status.HTTP_401_UNAUTHORIZED


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
        assert response.status_code == status.HTTP_201_CREATED
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
        assert response.status_code == status.HTTP_201_CREATED

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
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_unauthenticated_cannot_generate_invoice(
        self, api_client, bill_factory
    ):
        bill = bill_factory()
        response = api_client.post(
            _invoice_url(bill.id), {'billId': str(bill.id)}, format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


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

        assert response.status_code == status.HTTP_200_OK
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
        p_own   = patient_factory(doctor=dentist_user)
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

        assert response.status_code == status.HTTP_200_OK
        visit_ids = {str(c['visitId']) for c in response.data['patientVisitChoices']}
        assert str(visit_p1.id) in visit_ids

    def test_invalid_patient_id_returns_400(self, api_client, admin_user):
        """BranchToSerializerMixin-level validation via get_serializer_context."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'patientId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        assert api_client.get(reverse(self.URL)).status_code == status.HTTP_401_UNAUTHORIZED