import uuid
import pytest
from decimal import Decimal
from datetime import timedelta
from .utils import render_error
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from finances.models import Transaction
from patients.tasks import update_patient_insurance_usedYTD_task


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _transaction_url(transaction_id):
    return reverse('retrieve_update_delete_transaction', kwargs={'id': transaction_id})

def _create_payload(bill, visit=None, **overrides):
    base = {
        'billId': str(bill.id),
        'visitId': (str(visit.id) if visit else None),
        'date': str(timezone.localdate()),
        'amount': '150.00',
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

        assert response.status_code == status.HTTP_200_OK or render_error(response)
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
        p_own = patient_factory(doctor=dentist_user)
        p_other = patient_factory(doctor=other_dentist_user)
        b_own = bill_factory(patient=p_own, visits=[
            visit_factory(patient=p_own, doctor=dentist_user)
        ])
        b_other = bill_factory(patient=p_other, visits=[
            visit_factory(patient=p_other, doctor=other_dentist_user)
        ])
        transaction_own = transaction_factory(bill=b_own,   patient=p_own,   visit=b_own.visits.first())
        transaction_other = transaction_factory(bill=b_other, patient=p_other, visit=b_other.visits.first())

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [str(t['id']) for t in response.data['data']]
        assert str(transaction_own.id) in ids
        assert str(transaction_other.id) not in ids

    def test_assistant_without_view_transactions_permission_gets_403(
        self, api_client, assistant_user
    ):
        """receptionist has create.transaction but not view.transactions."""
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

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
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
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
        bill = bill_factory()
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
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_response_is_wrapped(self, api_client, admin_user, bill_factory):
        bill = bill_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(bill, bill.visits.first()), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

@pytest.mark.django_db
class TestTransactionListFields:

    def _list_item(self, api_client, txn):
        response = api_client.get(reverse('list_create_transactions'))
        return next(t for t in response.data['data'] if t['id'] == str(txn.id))

    def test_installment_plan_id_is_null_for_plain_bills_and_set_for_plan_bills(
        self, api_client, admin_user, transaction_factory, installment_plan_factory, plan_bill_factory
    ):
        plain = transaction_factory()
        plan = installment_plan_factory()
        plan_txn = transaction_factory(bill=plan_bill_factory(plan), type='installment')

        api_client.force_authenticate(user=admin_user)
        assert self._list_item(api_client, plain)['installmentPlanId'] is None
        assert str(self._list_item(api_client, plan_txn)['installmentPlanId']) == str(plan.id)

    def test_list_includes_the_type_of_each_transaction(self, api_client, admin_user, transaction_factory):
        txn = transaction_factory()
        api_client.force_authenticate(user=admin_user)
        assert self._list_item(api_client, txn)['type'] is not None

    def test_non_admin_sees_refunded_rows_with_status_and_type(
        self, api_client, user_factory, transaction_factory, refund_transaction
    ):
        """Fails if get_fields() still strips 'status' for non-admins; refunds are no longer hidden from them."""
        txn = refund_transaction(transaction=transaction_factory())
        api_client.force_authenticate(user=user_factory(role='accountant'))
        item = self._list_item(api_client, txn)

        assert 'status' in item
        assert 'type' in item

@pytest.mark.django_db
class TestCreateTransactionRules:
    URL = 'list_create_transactions'

    def _post(self, api_client, user, bill, visit=None, **overrides):
        api_client.force_authenticate(user=user)
        return api_client.post(reverse(self.URL), _create_payload(bill, visit, **overrides), format='json')

    def test_visit_is_optional_and_visit_totals_are_untouched(self, api_client, admin_user, bill_factory):
        bill = bill_factory()
        visit = bill.visits.first()
        response = self._post(api_client, admin_user, bill)

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        txn = Transaction.objects.get(bill=bill)
        assert txn.visit is None
        assert txn.patient == bill.patient
        visit.refresh_from_db()
        assert visit.paid == Decimal('150.00')   # factory default; a visit-less payment must not change it

    def test_type_is_visit_fee_when_visit_given_and_bill_has_no_treatment(self, api_client, admin_user, bill_factory):
        bill = bill_factory()
        self._post(api_client, admin_user, bill, visit=bill.visits.first())
        assert Transaction.objects.get(bill=bill).type == 'visit_fee'

    def test_type_is_treatment_payment_when_bill_has_treatment(
        self, api_client, admin_user, bill_factory, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory()
        treatment = treatment_plan_factory(patient=patient, procedure=procedure_factory())
        bill = bill_factory(patient=patient, treatment=treatment, visits=[])
        self._post(api_client, admin_user, bill)
        assert Transaction.objects.get(bill=bill).type == 'treatment_payment'

    def test_treatment_wins_over_visit_when_deriving_type(
        self, api_client, admin_user, bill_factory, patient_factory, procedure_factory, treatment_plan_factory,
        visit_factory, dentist_user
    ):
        patient = patient_factory()
        treatment = treatment_plan_factory(patient=patient, procedure=procedure_factory())
        visit = visit_factory(patient=patient, doctor=dentist_user)
        bill = bill_factory(patient=patient, treatment=treatment, visits=[visit])
        self._post(api_client, admin_user, bill, visit=visit)
        assert Transaction.objects.get(bill=bill).type == 'treatment_payment'

    def test_type_is_other_with_neither_visit_nor_treatment(self, api_client, admin_user, bill_factory):
        bill = bill_factory(visits=[])
        self._post(api_client, admin_user, bill)
        assert Transaction.objects.get(bill=bill).type == 'other'

    def test_negative_amount_returns_400(self, api_client, admin_user, bill_factory):
        bill = bill_factory()
        response = self._post(api_client, admin_user, bill, amount='-5.00')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert not Transaction.objects.filter(bill=bill).exists()

    # ── Rejections (fail until the validations in "Findings" 1 and 3 are added) ──

    def test_plain_transaction_on_installment_bill_is_rejected(
        self, api_client, admin_user, installment_plan_factory, plan_bill_factory
    ):
        plan = installment_plan_factory()
        bill = plan_bill_factory(plan)
        response = self._post(api_client, admin_user, bill)

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

        #plan total paid shouldn't have gotten changed
        plan.refresh_from_db()
        assert plan.totalPaid == Decimal('0') 

    def test_transaction_on_deposit_bill_is_rejected(self, api_client, admin_user, deposit_factory):
        deposit = deposit_factory(amount=Decimal('500.00'))
        response = self._post(api_client, admin_user, deposit.bill)

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        deposit.bill.refresh_from_db()
        assert deposit.bill.totalPaid == Decimal('500.00')

    def test_visit_of_another_patient_is_rejected(
        self, api_client, admin_user, bill_factory, patient_factory, visit_factory, dentist_user
    ):
        bill = bill_factory()
        other_visit = visit_factory(patient=patient_factory(), doctor=dentist_user)
        response = self._post(api_client, admin_user, bill, visit=other_visit)

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'visitId' in response.data['error']['fields']
        other_visit.refresh_from_db()
        assert other_visit.paid == Decimal('150.00')


# ══════════════════════════════════════════════════════════════════════════════
# PATCH | DELETE  /transactions/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdateDeleteTransactionAPIView:
    # ── PATCH (admin only) ────────────────────────────────────────────────────

    def test_admin_can_patch_transaction_amount(
        self, api_client, admin_user, transaction_factory
    ):
        transaction = transaction_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _transaction_url(transaction.id), {'amount': '300.00'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
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
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

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

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not Transaction.objects.filter(id=tid).exists()
        assert not Transaction.all_objects.filter(id=tid).exists()

    def test_admin_hard_delete_does_update_bill_total_paid_to_zero(
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
        assert bill.totalPaid == Decimal('0')

    def test_admin_hard_delete_recalculates_bill_and_visit_totals(
        self, api_client, admin_user, transaction_factory
    ):
        """pre_delete recomputes aggregates without the deleted row."""
        transaction = transaction_factory(amount=Decimal('150.00'))
        bill, visit = transaction.bill, transaction.visit
        bill.refresh_from_db()
        assert bill.totalPaid == Decimal('150.00')

        api_client.force_authenticate(user=admin_user)
        api_client.delete(_transaction_url(transaction.id))

        bill.refresh_from_db(); visit.refresh_from_db()
        assert bill.totalPaid == Decimal('0.00')
        assert visit.paid == Decimal('0.00')
        
    def test_non_admin_soft_deletes_transaction(
        self, api_client, user_factory, transaction_factory
    ):
        """Non-admin with delete.transaction soft-deletes (isDeleted=True)."""
        accountant = user_factory(role='accountant')
        transaction = transaction_factory()
        tid = transaction.id

        api_client.force_authenticate(user=accountant)
        response = api_client.delete(_transaction_url(tid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
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
        transaction = transaction_factory(amount=Decimal('150.00'))
        visit = transaction.visit
        visit.refresh_from_db()
        assert visit.paid == Decimal('150.00')   # set on creation

        api_client.force_authenticate(user=accountant)
        api_client.delete(_transaction_url(transaction.id))

        visit.refresh_from_db()
        assert visit.paid == Decimal('0.00')

    def test_unauthenticated_cannot_delete(self, api_client, transaction_factory):
        transaction = transaction_factory()
        response = api_client.delete(_transaction_url(transaction.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# Insurance payments — coverage rules and allowance tracking
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInsurancePayments:
    URL = 'list_create_transactions'

    def _post_insurance(self, api_client, user, bill, **overrides):
        api_client.force_authenticate(user=user)
        return api_client.post(
            reverse(self.URL), _create_payload(bill, method='insurance', **overrides), format='json'
        )

    @pytest.fixture
    def maxed_out_coverage(self, patient_factory, bill_factory, coverage_factory, transaction_factory):
        """A patient whose one insurance payment used the whole 10000 allowance."""
        patient = patient_factory()
        coverage = coverage_factory(patient)
        bill = bill_factory(patient=patient, subtotal=Decimal('10000.00'), totalAmount=Decimal('10000.00'))
        txn = transaction_factory(bill=bill, method='insurance', amount=Decimal('10000.00'))
        coverage.refresh_from_db()
        assert coverage.eligibilityStatus == 'limit_reached'
        return patient, coverage, bill, txn


    def test_insurance_payment_without_provider_returns_400(self, api_client, admin_user, bill_factory):
        bill = bill_factory()   # the patient's coverage row has no provider
        response = self._post_insurance(api_client, admin_user, bill)

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'method' in response.data['error']['fields']
        assert not Transaction.objects.filter(bill=bill).exists()

    def test_valid_insurance_payment_consumes_allowance(
        self, api_client, admin_user, patient_factory, bill_factory, coverage_factory
    ):
        patient = patient_factory()
        coverage = coverage_factory(patient)
        bill = bill_factory(patient=patient)
        response = self._post_insurance(api_client, admin_user, bill)

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('150.00')

    @pytest.mark.parametrize('eligibility', ['expired', 'limit_reached'])
    def test_inactive_coverage_blocks_insurance_payment(
        self, api_client, admin_user, patient_factory, bill_factory, coverage_factory, eligibility
    ):
        patient = patient_factory()
        coverage_factory(patient, eligibilityStatus=eligibility)
        response = self._post_insurance(api_client, admin_user, bill_factory(patient=patient))

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'method' in response.data['error']['fields']

    def test_unmet_deductible_blocks_insurance_payment(
        self, api_client, admin_user, patient_factory, bill_factory, coverage_factory
    ):
        patient = patient_factory()
        coverage_factory(patient, deductibleMet=False)   # provider covers 80%, so the deductible applies
        response = self._post_insurance(api_client, admin_user, bill_factory(patient=patient))

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_payment_exceeding_annual_max_is_blocked(
        self, api_client, admin_user, patient_factory, bill_factory, coverage_factory
    ):
        patient = patient_factory()
        coverage_factory(patient, usedYTD=Decimal('9950.00'))   # provider max is 10000
        response = self._post_insurance(api_client, admin_user, bill_factory(patient=patient))   # 150

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_cash_payment_ignores_coverage_state(
        self, api_client, admin_user, patient_factory, bill_factory, coverage_factory
    ):
        patient = patient_factory()
        coverage_factory(patient, eligibilityStatus='expired')
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), _create_payload(bill_factory(patient=patient)), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_refunding_an_insurance_payment_returns_the_allowance(
        self, patient_factory, bill_factory, coverage_factory, transaction_factory, refund_transaction
    ):
        patient = patient_factory()
        coverage = coverage_factory(patient)
        txn = transaction_factory(bill=bill_factory(patient=patient), method='insurance', amount=Decimal('150.00'))
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('150.00')

        refund_transaction(transaction=txn)

        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('0.00')

    def test_cash_payments_accumulate_toward_the_deductible(
        self, patient_factory, bill_factory, coverage_factory, insurance_provider_factory, transaction_factory
    ):
        provider = insurance_provider_factory(deductible=Decimal('100.00'))
        patient = patient_factory()
        coverage = coverage_factory(patient, provider=provider, deductibleMet=False)
        transaction_factory(bill=bill_factory(patient=patient), amount=Decimal('150.00'))

        coverage.refresh_from_db()
        assert coverage.deductibleMet is True

    def test_deposit_does_not_count_toward_the_deductible(
        self, patient_factory, bill_factory, coverage_factory, insurance_provider_factory,
        transaction_factory, deposit_factory, treatment_plan_factory, procedure_factory
    ):
        """Fails until the signal's deductible aggregate excludes type='deposit' (Findings 4)."""
        provider = insurance_provider_factory(deductible=Decimal('100.00'))
        patient = patient_factory()
        coverage = coverage_factory(patient, provider=provider, deductibleMet=False)
        treatment = treatment_plan_factory(patient=patient, procedure=procedure_factory())
        deposit_factory(treatment=treatment, amount=Decimal('500.00'))
        transaction_factory(bill=bill_factory(patient=patient), amount=Decimal('50.00'))   # below the deductible

        coverage.refresh_from_db()
        assert coverage.deductibleMet is False

    def test_patch_method_to_insurance_validates_coverage(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        """Fails until the method-change check is added (Findings 2)."""
        txn = transaction_factory(bill=bill_factory())   # cash; the patient has no provider
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(_transaction_url(txn.id), {'method': 'insurance'}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        txn.refresh_from_db()
        assert txn.method == 'cash'

    def test_patch_method_to_insurance_updates_allowance(
        self, api_client, admin_user, patient_factory, bill_factory, coverage_factory, transaction_factory
    ):
        patient = patient_factory()
        coverage = coverage_factory(patient)
        txn = transaction_factory(bill=bill_factory(patient=patient))
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(_transaction_url(txn.id), {'method': 'insurance'}, format='json')

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('150.00')

    # ── Insurance Coverage Rules ────────────────────────────────────────────────────────────────

    def test_refund_that_frees_allowance_restores_activity(self, maxed_out_coverage, refund_transaction):
        _, coverage, _, txn = maxed_out_coverage
        #assign `effectiveTo` date
        coverage.effectiveTo = timezone.localdate() + timedelta(days=45)
        coverage.save()

        refund_transaction(transaction=txn)
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('0.00')
        assert coverage.eligibilityStatus == 'active' 
        assert coverage.eligibilityChecked == timezone.localdate()

    def test_refund_that_leaves_usage_at_the_max_keeps_the_limit(
        self, maxed_out_coverage, bill_factory, transaction_factory, refund_transaction
    ):
        patient, coverage, _, _ = maxed_out_coverage
        extra = transaction_factory(bill=bill_factory(patient=patient), method='insurance', amount=Decimal('150.00'))
        refund_transaction(transaction=extra)   # usage is back to exactly 10000
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('10000.00')
        assert coverage.eligibilityStatus == 'limit_reached'

    def test_admin_delete_restores_activity(self, maxed_out_coverage, api_client, admin_user):
        _, coverage, _, txn = maxed_out_coverage
        #assign `effectiveTo` date
        coverage.effectiveTo = timezone.localdate() + timedelta(days=45)
        coverage.save()

        api_client.force_authenticate(user=admin_user)
        api_client.delete(_transaction_url(txn.id))
        coverage.refresh_from_db()
        assert coverage.eligibilityStatus == 'active'

    def test_changing_method_away_from_insurance_restores_activity(self, maxed_out_coverage, api_client, admin_user):
        _, coverage, _, txn = maxed_out_coverage
        #assign `effectiveTo` date
        coverage.effectiveTo = timezone.localdate() + timedelta(days=15)
        coverage.save()

        api_client.force_authenticate(user=admin_user)
        api_client.patch(_transaction_url(txn.id), {'method': 'cash'}, format='json')
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('0.00')
        assert coverage.eligibilityStatus == 'expiring'  #'expiring' bec date within a one-month window

    def test_reversing_the_refund_reinstates_the_limit(self, maxed_out_coverage, refund_transaction):
        _, coverage, _, txn = maxed_out_coverage
        refund_transaction(transaction=txn)
        txn.status = 'completed'
        txn.save()
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('10000.00')
        assert coverage.eligibilityStatus == 'limit_reached'

    def test_refund_does_not_touch_other_statuses(
        self, patient_factory, bill_factory, coverage_factory, transaction_factory, refund_transaction
    ):
        patient = patient_factory()
        coverage = coverage_factory(patient, eligibilityStatus='expired')
        txn = transaction_factory(bill=bill_factory(patient=patient), method='insurance', amount=Decimal('150.00'))
        refund_transaction(transaction=txn)
        coverage.refresh_from_db()
        assert coverage.eligibilityStatus == 'expired'

    def test_refund_with_no_annual_max_does_not_crash(
        self, patient_factory, bill_factory, coverage_factory, insurance_provider_factory,
        transaction_factory, refund_transaction
    ):
        provider = insurance_provider_factory(annualMax=None)
        patient = patient_factory()
        coverage = coverage_factory(patient, provider=provider, eligibilityStatus='limit_reached')        

        txn = transaction_factory(bill=bill_factory(patient=patient), method='insurance', amount=Decimal('150.00'))
        refund_transaction(transaction=txn)
        
        coverage.refresh_from_db()
        assert coverage.eligibilityStatus == 'active'

    @pytest.mark.parametrize('days_from_today, expected', [(-1, 'expired'), (10, 'expiring'), (200, 'active')])
    def test_restored_status_respects_the_policy_dates(
        self, maxed_out_coverage, refund_transaction, days_from_today, expected
    ):
        _, coverage, _, txn = maxed_out_coverage
        coverage.effectiveTo = timezone.localdate() + timedelta(days=days_from_today)
        coverage.save()
        refund_transaction(transaction=txn)
        coverage.refresh_from_db()
        assert coverage.eligibilityStatus == expected

    def test_yearly_reset_lifts_last_years_limit(self, maxed_out_coverage):
        _, coverage, _, _ = maxed_out_coverage
        update_patient_insurance_usedYTD_task()
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('0.00')
        assert coverage.eligibilityStatus != 'limit_reached'



# ══════════════════════════════════════════════════════════════════════════════
# Refunds and corrections (status changes; the row stays visible)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRefundsAndCorrections:

    def test_refund_removes_only_that_payment_from_bill_and_visit_totals(
        self, bill_factory, transaction_factory, refund_transaction
    ):
        bill = bill_factory()
        visit = bill.visits.first()
        first = transaction_factory(bill=bill, amount=Decimal('100.00'))
        transaction_factory(bill=bill, amount=Decimal('60.00'))

        refund_transaction(transaction=first)

        bill.refresh_from_db(); visit.refresh_from_db()
        assert bill.totalPaid == Decimal('60.00')
        assert visit.paid == Decimal('60.00')

    def test_refunded_transaction_is_not_soft_deleted(self, transaction_factory, refund_transaction):
        txn = refund_transaction(transaction=transaction_factory())
        assert txn.isDeleted is False
        assert Transaction.objects.filter(id=txn.id).exists()   #still reachable through the default manager

    def test_reversing_a_refund_restores_totals_and_clears_the_reason(
        self, bill_factory, transaction_factory, refund_transaction
    ):
        bill = bill_factory()
        txn = transaction_factory(bill=bill, amount=Decimal('100.00'))
        refund_transaction(transaction=txn, reason='Patient cancelled')
        txn.refresh_from_db()
        assert txn.refundReason == 'Patient cancelled'

        txn.status = 'completed'
        txn.save()

        txn.refresh_from_db(); bill.refresh_from_db()
        assert txn.refundReason is None
        assert bill.totalPaid == Decimal('100.00')

    def test_pending_correction_stays_in_circulation_and_reason_clears_when_resolved(
        self, bill_factory, transaction_factory
    ):
        bill = bill_factory()
        visit = bill.visits.first()
        txn = transaction_factory(bill=bill, amount=Decimal('100.00'))
        txn.status = 'pending_correction'
        txn.correctionReason = 'Wrong amount entered'
        txn.save(update_fields=['status', 'correctionReason'])

        bill.refresh_from_db(); visit.refresh_from_db()
        assert bill.totalPaid == Decimal('100.00')
        assert visit.paid == Decimal('100.00')

        txn.status = 'completed'
        txn.save()
        txn.refresh_from_db()
        assert txn.correctionReason is None

    def test_admin_can_refund_through_the_generic_patch(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        bill = bill_factory()
        txn = transaction_factory(bill=bill, amount=Decimal('100.00'))
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(_transaction_url(txn.id), {'status': 'refunded'}, format='json')

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        bill.refresh_from_db()
        assert bill.totalPaid == Decimal('0.00')


# ══════════════════════════════════════════════════════════════════════════════
# Deletes and refunds on installment-settling transactions
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInstallmentTransactionCascades:

    @pytest.fixture
    def settled(self, installment_plan_factory, plan_bill_factory, transaction_factory):
        plan = installment_plan_factory()
        bill = plan_bill_factory(plan)
        installment = plan.installments.get(sequence=1)
        txn = transaction_factory(bill=bill, patient=bill.patient, amount=installment.amount, type='installment')
        installment.transaction = txn
        installment.paidAt = timezone.now()
        installment.save()
        return plan, installment, txn

    def _assert_unlinked(self, plan, installment):
        installment.refresh_from_db(); plan.refresh_from_db()
        assert installment.paidAt is None
        assert installment.transaction_id is None
        assert plan.totalPaid == Decimal('0')

    def test_admin_hard_delete_unlinks_installments_and_resets_plan_total(self, api_client, admin_user, settled):
        plan, installment, txn = settled
        api_client.force_authenticate(user=admin_user)
        api_client.delete(_transaction_url(txn.id))
        self._assert_unlinked(plan, installment)

    def test_non_admin_soft_delete_unlinks_installments(self, api_client, user_factory, settled):
        plan, installment, txn = settled
        api_client.force_authenticate(user=user_factory(role='accountant'))
        api_client.delete(_transaction_url(txn.id))
        self._assert_unlinked(plan, installment)

    def test_refund_unlinks_installments(self, settled, refund_transaction):
        plan, installment, txn = settled
        refund_transaction(transaction=txn)
        self._assert_unlinked(plan, installment)


# ══════════════════════════════════════════════════════════════════════════════
# Refund endpoint (route name and PATCH method assumed above)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRefundTransactionAPI:

    def _refund(self, api_client, txn, **payload):
        return api_client.patch(reverse('refund_transaction', kwargs={'id': txn.id}), payload, format='json')

    def test_user_without_edit_permission_can_refund_with_a_reason(
        self, api_client, user_factory, bill_factory, transaction_factory
    ):
        bill = bill_factory()
        txn = transaction_factory(bill=bill, amount=Decimal('100.00'))
        api_client.force_authenticate(user=user_factory(role='accountant'))
        response = self._refund(api_client, txn, refundReason='Patient cancelled')

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        txn.refresh_from_db(); bill.refresh_from_db()
        assert txn.status == 'refunded'
        assert txn.refundReason == 'Patient cancelled'
        assert txn.isDeleted is False
        assert bill.totalPaid == Decimal('0.00')

    @pytest.mark.parametrize('payload', [{}, {'refundReason': ''}, {'refundReason': None}])
    def test_reason_is_required(self, api_client, admin_user, transaction_factory, payload):
        txn = transaction_factory()
        api_client.force_authenticate(user=admin_user)

        response = self._refund(api_client, txn, **payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        txn.refresh_from_db()
        assert txn.status == 'completed'

    def test_refund_cannot_change_the_amount(self, api_client, admin_user, transaction_factory):
        txn = transaction_factory(amount=Decimal('100.00'))
        api_client.force_authenticate(user=admin_user)
        self._refund(api_client, txn, refundReason='Mistake', amount='1.00')
        txn.refresh_from_db()
        assert txn.amount == Decimal('100.00')

    def test_user_without_transaction_permissions_gets_403(self, api_client, assistant_user, transaction_factory):
        api_client.force_authenticate(user=assistant_user)
        response = self._refund(api_client, transaction_factory(), refundReason='x')
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client, transaction_factory):
        response = self._refund(api_client, transaction_factory(), refundReason='x')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# Deposit endpoint (route name assumed above)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCreateDepositAPI:

    @staticmethod
    def _payload(patient, **overrides):
        base = {
            'patientId': str(patient.id),
            'date': str(timezone.localdate()),
            'amount': '500.00',
            'currency': '$',
            'branchId': None,
        }
        base.update(overrides)
        return base

    def _post(self, api_client, user, payload):
        api_client.force_authenticate(user=user)
        return api_client.post(reverse('create_deposit_transaction'), payload, format='json')

    def test_deposit_creates_a_dedicated_settled_bill(self, api_client, admin_user, patient_factory):
        patient = patient_factory()
        response = self._post(api_client, admin_user, self._payload(patient))

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        txn = Transaction.objects.get(patient=patient)
        bill = txn.bill
        assert (txn.type, txn.status, txn.createdBy) == ('deposit', 'completed', admin_user.name)
        assert bill.isDepositBill is True
        assert bill.isCreditHeld is True
        assert bill.totalAmount == bill.totalPaid == txn.amount == Decimal('500.00')
        assert bill.visits.count() == 0

    def test_deposit_can_be_linked_to_the_patients_treatment(
        self, api_client, admin_user, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient = patient_factory()
        treatment = treatment_plan_factory(patient=patient, procedure=procedure_factory())
        self._post(api_client, admin_user, self._payload(patient, treatmentId=str(treatment.id)))

        txn = Transaction.objects.get(patient=patient)
        assert txn.treatmentId == treatment.id
        assert txn.bill.treatment == treatment

    def test_treatment_of_another_patient_returns_400(
        self, api_client, admin_user, patient_factory, procedure_factory, treatment_plan_factory
    ):
        patient, other = patient_factory(), patient_factory()
        treatment = treatment_plan_factory(patient=other, procedure=procedure_factory())
        response = self._post(api_client, admin_user, self._payload(patient, treatmentId=str(treatment.id)))

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert not Transaction.objects.filter(type='deposit').exists()

    def test_unknown_treatment_returns_400(self, api_client, admin_user, patient_factory):
        response = self._post(api_client, admin_user, self._payload(patient_factory(), treatmentId=str(uuid.uuid4())))
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_insurance_method_is_rejected_without_creating_anything(self, api_client, admin_user, patient_factory):
        response = self._post(api_client, admin_user, self._payload(patient_factory(), method='insurance'))

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert not Transaction.objects.filter(type='deposit').exists()

    def test_negative_amount_returns_400(self, api_client, admin_user, patient_factory):
        response = self._post(api_client, admin_user, self._payload(patient_factory(), amount='-10.00'))
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_deposit_does_not_consume_the_insurance_allowance(
        self, api_client, admin_user, patient_factory, coverage_factory
    ):
        patient = patient_factory()
        coverage = coverage_factory(patient)
        self._post(api_client, admin_user, self._payload(patient))
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('0.00')

    def test_unauthenticated_gets_401(self, api_client, patient_factory):
        response = api_client.post(reverse('create_deposit_transaction'), self._payload(patient_factory()), format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


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

        assert response.status_code == status.HTTP_200_OK or render_error(response)
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
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)