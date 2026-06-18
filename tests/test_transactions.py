import uuid
import pytest
from datetime import date
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from finances.models import Transaction


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _transaction_url(transaction_id):
    return reverse('update_delete_transaction', kwargs={'id': transaction_id})

def _create_payload(bill, visit, **overrides):
    base = {
        'billId':  str(bill.id),
        'visitId': str(visit.id),
        'date':    str(date.today()),
        'amount':  '150.00',
        'currency': '$',
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /transactions/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateTransactionsAPIView:
    LIST_URL = 'list_create_transactions'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_transactions_including_deleted(
        self, api_client, admin_user, transaction_factory
    ):
        """Admin get_queryset uses Transaction.all_objects."""
        transaction = transaction_factory()
        transaction.isDeleted = True
        transaction.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK
        assert str(transaction.id) in [str(t['id']) for t in response.data['data']]

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, transaction_factory
    ):
        transaction_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data

    def test_soft_deleted_transactions_hidden_from_non_admin(
        self, api_client, user_factory, transaction_factory
    ):
        """Non-admin get_queryset uses Transaction.objects (isDeleted=False)."""
        accountant = user_factory(role='accountant')
        transaction = transaction_factory()
        transaction.isDeleted = True
        transaction.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=accountant)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(transaction.id) not in [str(t['id']) for t in response.data['data']]

    def test_dentist_sees_only_own_patients_transactions(
        self, api_client, dentist_user, other_dentist_user, patient_factory,
        visit_factory, bill_factory, transaction_factory
    ):
        """GET queryset: dentist path → filter(patient__doctor=user)."""
        p_own   = patient_factory(doctor=dentist_user)
        p_other = patient_factory(doctor=other_dentist_user)
        b_own   = bill_factory(patient=p_own, visits=[
            visit_factory(patient=p_own, doctor=dentist_user)
        ])
        b_other = bill_factory(patient=p_other, visits=[
            visit_factory(patient=p_other, doctor=other_dentist_user)
        ])
        transaction_own   = transaction_factory(bill=b_own,   patient=p_own,   visit=b_own.visits.first())
        transaction_other = transaction_factory(bill=b_other, patient=p_other, visit=b_other.visits.first())

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [str(t['id']) for t in response.data['data']]
        assert str(transaction_own.id) in ids
        assert str(transaction_other.id) not in ids

    def test_receptionist_without_view_transactions_gets_403(
        self, api_client, receptionist_user
    ):
        """receptionist has create.transaction but not view.transactions."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self, api_client):
        assert api_client.get(reverse(self.LIST_URL)).status_code == status.HTTP_401_UNAUTHORIZED

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_transaction(
        self, api_client, admin_user, bill_factory
    ):
        bill = bill_factory()
        visit = bill.visits.first()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(bill, visit),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Transaction.objects.filter(bill=bill).exists()

    def test_create_auto_sets_method_to_cash_when_omitted(
        self, api_client, admin_user, bill_factory
    ):
        """Transaction.save(): if not self.method → default to 'cash'."""
        bill = bill_factory()
        visit = bill.visits.first()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(bill, visit),
            format='json',
        )

        transaction = Transaction.objects.get(bill=bill)
        assert transaction.method == Transaction.PaymentMethodChoices.CASH

    def test_create_sets_snapshot_fields_from_related_objects(
        self, api_client, admin_user, bill_factory
    ):
        """Transaction.save(): patientName, billDescription captured on create."""
        bill = bill_factory()
        visit = bill.visits.first()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(bill, visit), format='json'
        )

        transaction = Transaction.objects.get(bill=bill)
        assert transaction.patientName == bill.patient.name
        assert transaction.billDescription == bill.description

    def test_create_sets_created_by_from_request_user(
        self, api_client, admin_user, bill_factory
    ):
        """validate() assigns createdBy = request.user.name."""
        bill = bill_factory()
        visit = bill.visits.first()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(bill, visit), format='json'
        )

        transaction = Transaction.objects.get(bill=bill)
        assert transaction.createdBy == admin_user.name

    def test_create_derives_patient_and_branch_from_bill(
        self, api_client, admin_user, bill_factory, branch
    ):
        """validate(): patient = bill.patient; branch = bill.branch."""
        bill = bill_factory(branch=branch)
        visit = bill.visits.first()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(bill, visit), format='json'
        )

        transaction = Transaction.objects.get(bill=bill)
        assert transaction.patient == bill.patient
        assert transaction.branch == branch

    def test_post_save_signal_updates_bill_total_paid(
        self, api_client, admin_user, bill_factory
    ):
        """post_save: bill.totalPaid = SUM(non-deleted transactions for this bill)."""
        bill = bill_factory()
        visit = bill.visits.first()
        bill.refresh_from_db()
        assert bill.totalPaid is None   #o transactions yet

        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(bill, visit, amount='250.00'),
            format='json',
        )

        bill.refresh_from_db()
        assert bill.totalPaid == Decimal('250.00')

    def test_post_save_signal_updates_visit_paid(
        self, api_client, admin_user, bill_factory
    ):
        """post_save: visit.paid = SUM(non-deleted transactions for this visit)."""
        bill  = bill_factory()
        visit = bill.visits.first()
        visit.refresh_from_db()
        initial_paid = visit.paid   #150.00' from visit_factory default

        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL),
            _create_payload(bill, visit, amount='300.00'),
            format='json',
        )

        visit.refresh_from_db()
        assert visit.paid == Decimal('300.00')
        assert visit.paid != initial_paid

    def test_user_with_create_transaction_permission_can_create(
        self, api_client, receptionist_user, bill_factory
    ):
        """receptionist has 'create.transaction' by default."""
        bill = bill_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(bill, bill.visits.first()),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_response_is_wrapped(self, api_client, admin_user, bill_factory):
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(bill, bill.visits.first()), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data


# ══════════════════════════════════════════════════════════════════════════════
# PATCH | DELETE  /transactions/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateDeleteTransactionAPIView:

    def test_get_method_not_allowed(
        self, api_client, admin_user, transaction_factory
    ):
        transaction = transaction_factory()
        api_client.force_authenticate(user=admin_user)
        assert api_client.get(_transaction_url(transaction.id)).status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # ── PATCH (admin only) ────────────────────────────────────────────────────

    def test_admin_can_patch_transaction_amount(
        self, api_client, admin_user, transaction_factory
    ):
        transaction = transaction_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _transaction_url(transaction.id), {'amount': '300.00'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        transaction.refresh_from_db()
        assert transaction.amount == Decimal('300.00')

    def test_non_admin_cannot_patch_transaction(
        self, api_client, user_factory, transaction_factory
    ):
        """get_permissions() returns AdminOnly for PATCH; any non-admin → 403."""
        accountant = user_factory(role='accountant')
        transaction = transaction_factory()
        api_client.force_authenticate(user=accountant)
        response = api_client.patch(
            _transaction_url(transaction.id), {'amount': '999.00'}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_read_only_fields_are_ignored(
        self, api_client, admin_user, transaction_factory, bill_factory
    ):
        """UpdateTransactionSerializer: billId, visitId, patientId, branchId are read_only."""
        transaction = transaction_factory()
        other_bill = bill_factory()
        original_bill_id = transaction.bill_id

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _transaction_url(transaction.id), {'billId': str(other_bill.id)}, format='json'
        )
        transaction.refresh_from_db()
        assert transaction.bill_id == original_bill_id   # unchanged

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_hard_deletes_transaction(
        self, api_client, admin_user, transaction_factory
    ):
        transaction = transaction_factory()
        tid = transaction.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_transaction_url(tid))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Transaction.objects.filter(id=tid).exists()
        assert not Transaction.all_objects.filter(id=tid).exists()

    def test_admin_hard_delete_does_not_update_bill_total_paid(
        self, api_client, admin_user, transaction_factory
    ):
        """
        Note: admin hard-delete fires post_delete (not post_save).
        The update_visit_paid signal only handles post_save, so bill.totalPaid
        is not recalculated after admin hard-delete.
        Thus, totalPaid on the bill shouldn't change after transaction deletion.
        """
        transaction = transaction_factory(amount=Decimal('150.00'))
        bill = transaction.bill
        bill.refresh_from_db()
        assert bill.totalPaid == Decimal('150.00')  #set by post_save on creation

        api_client.force_authenticate(user=admin_user)
        api_client.delete(_transaction_url(transaction.id))

        bill.refresh_from_db()
        assert bill.totalPaid == Decimal('150.00')

    def test_non_admin_soft_deletes_transaction(
        self, api_client, user_factory, transaction_factory
    ):
        """Non-admin with delete.transaction soft-deletes (isDeleted=True)."""
        accountant = user_factory(role='accountant')
        transaction = transaction_factory()
        tid = transaction.id

        api_client.force_authenticate(user=accountant)
        response = api_client.delete(_transaction_url(tid))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Transaction.objects.filter(id=tid).exists()
        deleted = Transaction.all_objects.get(id=tid)
        assert deleted.isDeleted is True

    def test_soft_delete_signal_recalculates_bill_total_paid(
        self, api_client, user_factory, transaction_factory
    ):
        """
        Non-admin soft-delete calls transaction.save() → post_save fires →
        signal recalculates bill.totalPaid using Transaction.objects
        (isDeleted=False), so the deleted transaction is excluded → 0.
        """
        accountant = user_factory(role='accountant')
        transaction = transaction_factory(amount=Decimal('150.00'))
        bill = transaction.bill
        bill.refresh_from_db()
        assert bill.totalPaid == Decimal('150.00')   # set on creation

        api_client.force_authenticate(user=accountant)
        api_client.delete(_transaction_url(transaction.id))

        bill.refresh_from_db()
        assert bill.totalPaid == Decimal('0.00')   # recalculated, soft-deleted excluded

    def test_soft_delete_signal_recalculates_visit_paid(
        self, api_client, user_factory, transaction_factory
    ):
        """post_save signal also recalculates visit.paid after soft-delete."""
        accountant = user_factory(role='accountant')
        transaction  = transaction_factory(amount=Decimal('150.00'))
        visit = transaction.visit
        visit.refresh_from_db()
        assert visit.paid == Decimal('150.00')   # set on creation

        api_client.force_authenticate(user=accountant)
        api_client.delete(_transaction_url(transaction.id))

        visit.refresh_from_db()
        assert visit.paid == Decimal('0.00')

    def test_unauthenticated_cannot_delete(self, api_client, transaction_factory):
        transaction = transaction_factory()
        assert api_client.delete(_transaction_url(transaction.id)).status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# GET  /transactions/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveTransactionsOptionsAPIView:
    """Plain generics.GenericAPIView + BranchToSerializerMixin. No ResponseMixin."""
    URL = 'transactions_options'

    def test_authenticated_user_gets_options_payload(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        for key in ('branchChoices', 'billChoices', 'patientChoices',
                    'patientVisitChoices', 'paymentMethodChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        assert 'success' not in api_client.get(reverse(self.URL)).data

    def test_payment_method_choices_cover_all_methods(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['paymentMethodChoices']}
        expected = {c.value for c in Transaction.PaymentMethodChoices}
        assert returned == expected

    def test_visit_choices_filtered_by_patient_id(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        """get_patientVisitChoices: patientId QP filters to that patient's visits."""
        p1 = patient_factory()
        p2 = patient_factory()
        v1 = visit_factory(patient=p1, doctor=dentist_user)
        v2 = visit_factory(patient=p2, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'patientId': str(p1.id)})

        visit_ids = {str(c['visitId']) for c in response.data['patientVisitChoices']}
        assert str(v1.id) in visit_ids
        assert str(v2.id) not in visit_ids

    def test_invalid_patient_id_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'patientId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        assert api_client.get(reverse(self.URL)).status_code == status.HTTP_401_UNAUTHORIZED