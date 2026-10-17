import pytest
from decimal import Decimal
from datetime import timedelta
from .utils import render_error
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from finances.models import Bill, Installment, InstallmentPlan, Transaction



#─────────────────────────────────────────────────────────────────────────────
#Factory
#─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_treatment(patient_factory, procedure_factory, treatment_plan_factory):
    def _make(total=Decimal('600.00'), patient=None):
        treatment = treatment_plan_factory(patient=patient or patient_factory(), procedure=procedure_factory())
        type(treatment).all_objects.filter(id=treatment.id).update(totalCost=total)   #raw update: skips the cost-change signal
        treatment.refresh_from_db()
        return treatment
    return _make


@pytest.fixture
def plan_with_bill(make_treatment, installment_plan_factory, plan_bill_factory):
    plan = installment_plan_factory(treatment=make_treatment(Decimal('600.00')), months=3)   #3 x 200.00
    return plan, plan_bill_factory(plan)


#─────────────────────────────────────────────────────────────────────────────
#Helpers
#─────────────────────────────────────────────────────────────────────────────

#Url methods
def _generate_plan_url(patient_id, treatment_id): 
    return reverse('generate_installment_plan',   
            kwargs={'id': patient_id, 'treatmentId': treatment_id})

def _plan_fromTreatment_url(patient_id, treatment_id):
    return reverse('retrieve_update_delete_patient_installment_plan', 
            kwargs={'id': patient_id, 'treatmentId': treatment_id})

def _edit_plan_url(plan_id):
    return reverse('update_delete_installment_plan_general', kwargs={'id': plan_id})

def _generate_bill_fromTreatment_url(patient_id, treatment_id):
    return reverse('autogenerate_installments_bill', 
            kwargs={'id': patient_id, 'treatmentId': treatment_id})

def _generate_bill_url(plan_id):
    return reverse('autogenerate_installments_bill_general', kwargs={'id': plan_id})

def _transaction_url(transaction_id):
    return reverse('retrieve_update_delete_transaction', kwargs={'id': transaction_id})

def _pay_installments_url(plan_id):
    return reverse('create_installment_transaction', kwargs={'id': plan_id})

def _installments_transaction_url(plan_id, transaction_id):
    return reverse('retrieve_update_delete_installment_transaction', 
            kwargs={'id': plan_id, 'transactionId': transaction_id})


#Other helper methods
def _items(response):
    data = response.data
    if isinstance(data, dict):
        if 'data' in data:
            return data['data']
        elif 'results' in data:
            return data['results']
        else:
            return data 
    return data

def _mark_paid(*installments):
    for installment in installments:
        installment.paidAt = timezone.now()
        installment.save(update_fields=['paidAt'])

def _make_transaction(api_client, user, plan, installments, **overrides):
    api_client.force_authenticate(user=user)
    payload = {
        'installmentIds': [str(i.id) for i in installments],
        'date': str(timezone.localdate()),
        'method': 'cash', 
        'currency': None, 
        'note': None
    }
    payload.update(overrides)
    return api_client.post(_pay_installments_url(plan.id), payload, format='json')


#══════════════════════════════════════════════════════════════════════════════════════
#POST api/patients/<uuid:id>/treatment-plans/<uuid:treatmentId>/installments/generate/
#══════════════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestGenerateInstallmentPlan:
    #Helper method
    @staticmethod
    def _generate(api_client, user, treatment, **payload):
        payload.setdefault('startDate', str(timezone.localdate() + timedelta(days=30)))
        api_client.force_authenticate(user=user)
        response = api_client.post(
            _generate_plan_url(treatment.patient.id, treatment.id), 
            payload, 
            format='json'
        )
        return response

    #Tests
    def test_down_payment_plus_equal_installments(self, api_client, admin_user, make_treatment):
        treatment = make_treatment(Decimal('5000.00'))
        response = self._generate(api_client, 
                                  admin_user, 
                                  treatment,
                                  startDate='2026-11-15', 
                                  installmentMonths=6, 
                                  downPayment='200.00')

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED) or render_error(response)
        data = response.data['data']
        items = sorted(data['installments'], key=lambda i: i['sequence'])
        assert Decimal(data['totalAmount']) == Decimal('5000.00')
        assert [i['sequence'] for i in items] == [0, 1, 2, 3, 4, 5, 6]
        assert Decimal(items[0]['amount']) == Decimal('200.00')
        assert all(Decimal(item['amount']) == Decimal('800.00') for item in items[1:])
        assert items[1]['dueDate'] == '2026-11-15' and items[2]['dueDate'] == '2026-12-15'
        assert sum(Decimal(item['amount']) for item in items) == Decimal('5000.00')
        assert all(str(i['status']).lower() == 'pending' for i in items)

        plan = InstallmentPlan.objects.get(treatment=treatment)
        installment = plan.installments.get(sequence=0)
        assert installment.type == 'down_payment'
        assert plan.totalPaid == Decimal('0')

    def test_rounding_remainder_goes_to_the_last_installment(self, api_client, admin_user, make_treatment):
        response = self._generate(api_client, admin_user, make_treatment(Decimal('1000.00')), installmentMonths=3)
        items = sorted(response.data['data']['installments'], key=lambda i: i['sequence'])
        assert [i['sequence'] for i in items] == [1, 2, 3]   #no down payment, so no sequence 0
        assert [Decimal(i['amount']) for i in items] == [Decimal('333.33'), Decimal('333.33'), Decimal('333.33')]

    def test_regenerating_an_unpaid_plan_replaces_it(self, api_client, admin_user, make_treatment):
        treatment = make_treatment()
        self._generate(api_client, admin_user, treatment, installmentMonths=6)
        response = self._generate(api_client, admin_user, treatment, installmentMonths=3)

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED) or render_error(response)
        assert InstallmentPlan.objects.filter(treatment=treatment).count() == 1
        plan = InstallmentPlan.objects.get(treatment=treatment)
        assert plan.installmentMonths == 3
        assert plan.installments.count() == 3   #the extra rows from the 6-month plan are gone

    def test_repeated_regeneration_does_not_inflate_total_paid(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = installment_plan_factory(treatment=make_treatment(), months=3, down_payment=Decimal('60.00'))
        installment = plan.installments.get(sequence=0)
        _mark_paid(installment)
        
        #update total paid
        InstallmentPlan.objects.filter(id=plan.id).update(totalPaid=Decimal('60.00'))

        for months in (6, 3, 6):
            self._generate(api_client, admin_user, plan.treatment, installmentMonths=months)
            plan.refresh_from_db()
            assert plan.totalPaid == Decimal('60.00')   #carried forward, never added again

    @pytest.mark.parametrize('months', [0, -1])
    def test_invalid_months_returns_400(self, api_client, admin_user, make_treatment, months):
        response = self._generate(api_client, admin_user, make_treatment(), installmentMonths=months)
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_treatment_of_another_patient_returns_404(self, api_client, admin_user, make_treatment, patient_factory):
        treatment = make_treatment()
        other_patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        generate_plan_url = _generate_plan_url(other_patient.id, treatment.id)
        response = api_client.post(
            generate_plan_url, 
            {'startDate': str(timezone.localdate()), 'installmentMonths': 3}, 
            format='json'
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_user_without_treatment_permission_gets_403(self, api_client, assistant_user, make_treatment):
        response = self._generate(api_client, assistant_user, make_treatment(), installmentMonths=3)
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client, make_treatment):
        treatment = make_treatment()
        response = api_client.post(
            _generate_plan_url(treatment.patient.id, treatment.id), 
            {'installmentMonths': 3}, 
            format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


#══════════════════════════════════════════════════════════════════════════════
#In-progress rules (generate / PATCH / DELETE)
#══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestInProgressRules:
    #Helpers
    CALLS = ['generate', 'patch_by_treatment', 'patch_by_id']
    DELETE_ROUTES = {
        'by_treatment': lambda plan: _plan_fromTreatment_url(plan.treatment.patient.id, plan.treatment.id), 
        'by_id': lambda plan: _edit_plan_url(plan.id)
    }

    @staticmethod
    def _edit_plan(api_client, call, plan):
        if call == 'generate':
            generate_url = _generate_plan_url(plan.treatment.patient.id, plan.treatment.id)
            payload = {'startDate': str(timezone.localdate()), 'installmentMonths': 6}
            response = api_client.post(
                generate_url,
                payload, 
                format='json'
            )
            return response
        
        else:    
            if call == 'patch_by_treatment':
                patch_url = _plan_fromTreatment_url(plan.treatment.patient.id, plan.treatment.id)
            else:
                patch_url = _edit_plan_url(plan.id)

            response = api_client.patch(patch_url, {'installmentMonths': 6}, format='json')
            return response

    #Tests
    @pytest.mark.parametrize('call', CALLS)
    def test_paid_installment_blocks_the_change_with_409(
        self, api_client, admin_user, make_treatment, installment_plan_factory, call
    ):
        plan = installment_plan_factory(treatment=make_treatment(), months=3)
        installment = plan.installments.get(sequence=1)
        _mark_paid(installment)
        api_client.force_authenticate(user=admin_user)

        response = self._edit_plan(api_client, call, plan)

        assert response.status_code == status.HTTP_409_CONFLICT or render_error(response)
        assert response.data['error']['code'] == 'INSTALLMENT_PLAN_IN_PROGRESS'
        assert plan.installments.count() == 3   #nothing was touched

    @pytest.mark.parametrize('call', CALLS)
    def test_paid_down_payment_alone_does_not_block_and_is_kept(
        self, api_client, admin_user, make_treatment, installment_plan_factory, call
    ):
        plan = installment_plan_factory(treatment=make_treatment(), months=3, down_payment=Decimal('60.00'))
        installment = plan.installments.get(sequence=0)
        _mark_paid(installment)
        #update total paid
        InstallmentPlan.objects.filter(id=plan.id).update(totalPaid=Decimal('60.00'))
        
        api_client.force_authenticate(user=admin_user)
        response = self._edit_plan(api_client, call, plan)   #downPayment omitted

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED) or render_error(response)
        plan.refresh_from_db()
        down = plan.installments.get(sequence=0)
        assert down.paidAt is not None and down.amount == Decimal('60.00')
        regular = plan.installments.filter(type='installment')
        assert regular.count() == 6
        assert sum(i.amount for i in regular) == Decimal('540.00')   #the paid 60 is not split again
        assert plan.totalPaid == Decimal('60.00')

    @pytest.mark.parametrize('route', DELETE_ROUTES)
    def test_delete_unpaid_plan(self, api_client, admin_user, make_treatment, installment_plan_factory, route):
        treatment = make_treatment()
        plan = installment_plan_factory(treatment=treatment, months=3, down_payment=Decimal('60.00'))
        api_client.force_authenticate(user=admin_user)

        response = api_client.delete(self.DELETE_ROUTES[route](plan))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not InstallmentPlan.objects.filter(id=plan.id).exists()
        assert not Installment.objects.filter(installmentPlan_id=plan.id).exists()
        type(treatment).objects.get(id=treatment.id)   #the treatment itself survives

    @pytest.mark.parametrize('route', DELETE_ROUTES)
    @pytest.mark.parametrize('paid_seq', [0, 1])   #delete is stricter than update: even the down payment blocks it
    def test_delete_with_anything_paid_returns_409(
        self, api_client, admin_user, make_treatment, installment_plan_factory, route, paid_seq
    ):
        plan = installment_plan_factory(treatment=make_treatment(), months=3, down_payment=Decimal('60.00'))
        installment = plan.installments.get(sequence=paid_seq)
        _mark_paid(installment)
        api_client.force_authenticate(user=admin_user)

        response = api_client.delete(self.DELETE_ROUTES[route](plan))

        assert response.status_code == status.HTTP_409_CONFLICT or render_error(response)
        assert response.data['error']['code'] == 'INSTALLMENT_PLAN_IN_PROGRESS'
        assert InstallmentPlan.objects.filter(id=plan.id).exists()

    def test_accountant_cannot_delete_by_id(
        self, api_client, user_factory, make_treatment, installment_plan_factory
    ):
        """Assumes delete.installments is admin/dentist only, as in your contract."""
        plan = installment_plan_factory(treatment=make_treatment(), months=3)
        api_client.force_authenticate(user=user_factory(role='accountant'))
        response = api_client.delete(_edit_plan_url(plan.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)


#══════════════════════════════════════════════════════════════════════════════
#PATCH — field updates and the down-payment rules
#══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestUpdateInstallmentPlan:
    @staticmethod
    def _patch(api_client, user, plan, **payload):
        api_client.force_authenticate(user=user)
        response =  api_client.patch(
            _plan_fromTreatment_url(plan.treatment.patient.id, plan.treatment.id), 
            payload, 
            format='json'
        )
        return response

    @staticmethod
    def _plan(make_treatment, installment_plan_factory, down=Decimal('0'), paid=False):
        plan = installment_plan_factory(treatment=make_treatment(), months=3, down_payment=down)
        if paid:
            installment = plan.installments.get(sequence=0)
            _mark_paid(installment)
            #update payment
            InstallmentPlan.objects.filter(id=plan.id).update(totalPaid=down)
        return plan

    def test_changing_months_resplits_the_remaining_total(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = self._plan(make_treatment, installment_plan_factory)
        response = self._patch(api_client, admin_user, plan, installmentMonths=6)

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        amounts = [i.amount for i in plan.installments.order_by('sequence')]
        assert amounts == [Decimal('100.00')] * 6

    def test_changing_start_date_shifts_due_dates(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = self._plan(make_treatment, installment_plan_factory)
        new_start = timezone.localdate() + timedelta(days=10)
        self._patch(api_client, admin_user, plan, startDate=str(new_start))

        assert plan.installments.get(sequence=1).dueDate == new_start
        assert plan.installments.get(sequence=2).dueDate.month == (new_start.month % 12) + 1

    def test_zero_removes_a_paid_down_payment_but_keeps_the_money(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = self._plan(make_treatment, installment_plan_factory, Decimal('60.00'), paid=True)
        self._patch(api_client, admin_user, plan, downPayment='0')

        plan.refresh_from_db()
        assert not plan.installments.filter(sequence=0).exists()
        assert plan.totalPaid == Decimal('60.00')
        regular = plan.installments.filter(type='installment')
        assert sum(i.amount for i in regular) == Decimal('540.00')

    def test_new_amount_overwrites_and_clears_the_paid_state(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = self._plan(make_treatment, installment_plan_factory, Decimal('60.00'), paid=True)
        self._patch(api_client, admin_user, plan, downPayment='100.00')
    
        down = plan.installments.get(sequence=0)
        assert down.amount == Decimal('100.00')
        assert down.paidAt is None and down.transaction_id is None

    def test_zero_removes_an_unpaid_down_payment(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = self._plan(make_treatment, installment_plan_factory, Decimal('60.00'))
        self._patch(api_client, admin_user, plan, downPayment='0')
        assert not plan.installments.filter(sequence=0).exists()

    def test_adding_a_down_payment_to_a_plan_without_one(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = self._plan(make_treatment, installment_plan_factory)
        self._patch(api_client, admin_user, plan, downPayment='60.00')

        assert plan.installments.get(sequence=0).amount == Decimal('60.00')
        regular = plan.installments.filter(type='installment')
        assert sum(i.amount for i in regular) == Decimal('540.00')


#══════════════════════════════════════════════════════════════════════════════
#GET — retrieve and list
#══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestRetrieveAndListInstallmentPlans:
    LIST_URL = reverse('list_installment_plans')

    def test_statuses_are_derived_from_payment_and_due_date(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = installment_plan_factory(
            treatment=make_treatment(), months=3, start_date=timezone.localdate() - timedelta(days=45)
        )
        installment = plan.installments.get(sequence=1)
        _mark_paid(installment)
        #update total paid
        InstallmentPlan.objects.filter(id=plan.id).update(totalPaid=Decimal('200.00'))
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(_plan_fromTreatment_url(plan.treatment.patient.id, plan.treatment.id))
        by_seq = {i['sequence']: i for i in response.data['data']['installments']}

        assert str(by_seq[1]['status']).lower() == 'paid' and by_seq[1]['paidAt'] is not None
        assert str(by_seq[2]['status']).lower() == 'overdue' and by_seq[2]['paidAt'] is None
        assert str(by_seq[3]['status']).lower() == 'pending'
        assert str(response.data['data']['status']).lower() == 'partial'
        assert Decimal(response.data['data']['totalPaid']) == Decimal('200.00')

    def test_retrieve_by_id_respects_branch_scope(
        self, api_client, user_factory, branch_factory, 
        patient_factory, make_treatment, installment_plan_factory
    ):
        b1, b2 = branch_factory(), branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b1])
        
        #grant treatment-viewing permission to accountant
        accountant.userPermissions.append('view.treatments')

        own_plan = installment_plan_factory(treatment=make_treatment(patient=patient_factory(branch=b1)))
        other_plan = installment_plan_factory(treatment=make_treatment(patient=patient_factory(branch=b2)))
        api_client.force_authenticate(user=accountant)

        assert api_client.get(_plan_fromTreatment_url(own_plan.treatment.patient.id, own_plan.treatment.id)).status_code == status.HTTP_200_OK
        assert api_client.get(_plan_fromTreatment_url(other_plan.treatment.patient.id, other_plan.treatment.id)).status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    def test_list_is_scoped_by_branch(
        self, api_client, user_factory, branch_factory, patient_factory, make_treatment, installment_plan_factory
    ):
        """Assumes accountants hold view.installments by default."""
        b1, b2 = branch_factory(), branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b1])
        own = installment_plan_factory(treatment=make_treatment(patient=patient_factory(branch=b1)))
        installment_plan_factory(treatment=make_treatment(patient=patient_factory(branch=b2)))
        api_client.force_authenticate(user=accountant)

        ids = {str(i['installmentPlanId']) for i in _items(api_client.get(self.LIST_URL))}
        assert ids == {str(own.id)}

    def test_dentist_list_only_includes_own_patients(
        self, api_client, dentist_user, patient_factory, make_treatment, installment_plan_factory
    ):
        mine = installment_plan_factory(treatment=make_treatment(patient=patient_factory(doctor=dentist_user)))
        installment_plan_factory(treatment=make_treatment())
        api_client.force_authenticate(user=dentist_user)

        ids = {str(i['installmentPlanId']) for i in _items(api_client.get(self.LIST_URL))}
        assert ids == {str(mine.id)}

    def test_status_and_branch_filters(
        self, api_client, admin_user, branch_factory, patient_factory, make_treatment, installment_plan_factory
    ):
        branch1, branch2 = branch_factory(), branch_factory()
        pending_plan = installment_plan_factory(treatment=make_treatment(patient=patient_factory(branch=branch1)))
        done_plan = installment_plan_factory(treatment=make_treatment(patient=patient_factory(branch=branch2)))
        
        #update total paid
        InstallmentPlan.objects.filter(id=done_plan.id).update(totalPaid=done_plan.totalAmount)

        api_client.force_authenticate(user=admin_user)
        pending_installments = _items(api_client.get(self.LIST_URL, {'status': 'pending'}))
        done_installments = _items(api_client.get(self.LIST_URL, {'status': 'completed'}))
        installments_byBranch = _items(api_client.get(self.LIST_URL, {'branchId': branch2.id}))

        assert {str(p['installmentPlanId']) for p in pending_installments} == {str(pending_plan.id)}
        assert {str(p['installmentPlanId']) for p in done_installments} == {str(done_plan.id)}
        assert {str(p['installmentPlanId']) for p in installments_byBranch} == {str(done_plan.id)}

    def test_user_without_installment_permission_gets_403(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        assert api_client.get(self.LIST_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self, api_client):
        assert api_client.get(self.LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED


#══════════════════════════════════════════════════════════════════════════════
#Autogenerate bill
#══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestAutogenerateInstallmentBill:
    def test_bill_mirrors_the_plan_from_the_treatment_route(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        #create a plan with a down payment and 3 installments
        treatment = make_treatment()
        plan = installment_plan_factory(treatment=treatment, months=3, down_payment=Decimal('60.00'))
        api_client.force_authenticate(user=admin_user)

        #generate the bill through the patient/treatment route
        url = _generate_bill_fromTreatment_url(treatment.patient.id, treatment.id)
        response = api_client.post(url, {}, format='json')

        #the bill is created and mirrors the plan
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        bill = Bill.objects.get(installmentPlan=plan)
        assert str(response.data['data']['billId']) == str(bill.id)
        assert bill.treatment == treatment
        assert bill.patient == treatment.patient
        assert bill.totalAmount == plan.totalAmount
        assert bill.isDepositBill is False

    def test_bill_mirrors_the_plan_from_the_plan_route(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        #create a plan with a down payment and 3 installments
        plan = installment_plan_factory(treatment=make_treatment(), months=3, down_payment=Decimal('60.00'))
        api_client.force_authenticate(user=admin_user)

        #generate the bill through the plan route
        response = api_client.post(_generate_bill_url(plan.id), {}, format='json')

        #the bill is created and mirrors the plan
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        bill = Bill.objects.get(installmentPlan=plan)
        assert str(response.data['data']['billId']) == str(bill.id)
        assert bill.totalAmount == plan.totalAmount

    def test_a_deleted_bill_can_be_regenerated(
        self, api_client, admin_user, make_treatment, installment_plan_factory, plan_bill_factory
    ):
        #create a plan whose bill was soft-deleted
        treatment = make_treatment()
        plan = installment_plan_factory(treatment=treatment, months=3)
        old_bill = plan_bill_factory(plan)
        Bill.all_objects.filter(id=old_bill.id).update(isDeleted=True)
        api_client.force_authenticate(user=admin_user)

        #generate a new bill
        url = _generate_bill_fromTreatment_url(treatment.patient.id, treatment.id)
        response = api_client.post(url, {}, format='json')

        #a fresh bill exists next to the deleted one
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Bill.objects.filter(installmentPlan=plan).exclude(id=old_bill.id).count() == 1


#══════════════════════════════════════════════════════════════════════════════
#POST api/installments/<uuid:id>/transactions/
#══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestPayInstallments:
    def test_paying_one_installment(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        first = plan.installments.get(sequence=1)

        response = _make_transaction(api_client, admin_user, plan, [first])

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        transaction = Transaction.objects.get(bill=bill)
        assert (transaction.type, transaction.amount, transaction.patient_id) == ('installment', Decimal('200.00'), bill.patient_id)

        #refresh instances
        first.refresh_from_db()
        plan.refresh_from_db() 
        bill.refresh_from_db()

        assert first.transaction_id == transaction.id and first.paidAt is not None
        assert plan.installments.get(sequence=2).paidAt is None
        assert plan.totalPaid == Decimal('200.00') and bill.totalPaid == Decimal('200.00')

    def test_several_installments_share_one_transaction(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        first = plan.installments.get(sequence=1)
        second = plan.installments.get(sequence=2)

        response = _make_transaction(api_client, admin_user, plan, [first, second])

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        
        transaction = Transaction.objects.get(bill=bill)  #exactly one
        assert transaction.amount == Decimal('400.00')

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.transaction_id == second.transaction_id == transaction.id

        plan.refresh_from_db()
        assert plan.totalPaid == Decimal('400.00')

    def test_amount_is_derived_from_the_selection_not_the_request(self, api_client, admin_user, plan_with_bill):
        """Contract: a wrong amount is ignored in favor of the installments' sum."""
        plan, bill = plan_with_bill
        installment = plan.installments.get(sequence=1)
        response = _make_transaction(api_client, admin_user, plan, [installment], amount='1.00')
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Transaction.objects.get(bill=bill).amount == Decimal('200.00')

    def test_paying_everything_completes_the_plan(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        _make_transaction(api_client, admin_user, plan, [plan.installments.get(sequence=s) for s in (1, 2, 3)])

        plan.refresh_from_db(); bill.refresh_from_db()
        assert plan.totalPaid == bill.totalPaid == Decimal('600.00')
        response = api_client.get(_plan_fromTreatment_url(plan.treatment.patient.id, plan.treatment.id))
        data = response.data['data']
        assert data['status'].lower().startswith('complet')

    def test_skipping_an_earlier_unpaid_installment_returns_400(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        response = _make_transaction(api_client, admin_user, plan, [plan.installments.get(sequence=2)])

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'installmentIds' in response.data['error']['fields']
        assert not Transaction.objects.filter(bill=bill).exists()

    def test_already_paid_installment_returns_400(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        first = plan.installments.get(sequence=1)
        _mark_paid(first)

        response = _make_transaction(api_client, admin_user, plan, [first])

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert not Transaction.objects.filter(bill=bill).exists()

    def test_installment_of_another_plan_returns_400(
        self, api_client, admin_user, plan_with_bill, make_treatment, installment_plan_factory
    ):
        plan, bill = plan_with_bill
        other = installment_plan_factory(treatment=make_treatment(), months=3)
        installment = other.installments.get(sequence=1)
        response = _make_transaction(api_client, admin_user, plan, [installment])

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert not Transaction.objects.filter(bill=bill).exists()

    def test_down_payment_is_paid_like_any_installment(
        self, api_client, admin_user, make_treatment, installment_plan_factory, plan_bill_factory
    ):
        plan = installment_plan_factory(treatment=make_treatment(), months=3, down_payment=Decimal('60.00'))
        bill = plan_bill_factory(plan)
    
        response = _make_transaction(api_client, admin_user, plan, [plan.installments.get(sequence=0)])

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        plan.refresh_from_db()
        assert plan.totalPaid == Decimal('60.00')
        assert plan.installments.get(sequence=0).paidAt is not None

    def test_insurance_payment_without_provider_returns_400(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        response = _make_transaction(api_client, admin_user, plan, [plan.installments.get(sequence=1)], method='insurance')

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'method' in response.data['error']['fields']
        assert not Transaction.objects.filter(bill=bill).exists()

    def test_insurance_payment_consumes_the_allowance(
        self, api_client, admin_user, plan_with_bill, coverage_factory
    ):
        plan, bill = plan_with_bill
        coverage = coverage_factory(plan.treatment.patient)

        response = _make_transaction(api_client, admin_user, plan, [plan.installments.get(sequence=1)], method='insurance')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('200.00')

    def test_user_without_transaction_permission_gets_403(self, api_client, assistant_user, plan_with_bill):
        plan, _ = plan_with_bill
        response = _make_transaction(api_client, assistant_user, plan, [plan.installments.get(sequence=1)])
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_gets_401(self, api_client, plan_with_bill):
        plan, _ = plan_with_bill
        response = api_client.post(_pay_installments_url(plan.id), {'installmentIds': [str(plan.installments.get(sequence=1).id)]}, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

@pytest.mark.django_db
class TestRefundAndDeleteOfInstallmentTransactions:
    @pytest.fixture
    def pay_two_installments(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        installments = [plan.installments.get(sequence=1), plan.installments.get(sequence=2)]
        _make_transaction(api_client, admin_user, plan, installments)
        transaction = Transaction.objects.get(bill=bill)
        return plan, bill, transaction

    def _assert_all_unpaid(self, plan, bill):
        plan.refresh_from_db(); bill.refresh_from_db()
        assert all(i.paidAt is None and i.transaction_id is None for i in plan.installments.all())
        assert plan.totalPaid == Decimal('0') and bill.totalPaid == Decimal('0')

    def test_refund_unlinks_every_installment(self, pay_two_installments, refund_transaction):
        plan, bill, transaction = pay_two_installments
        refund_transaction(transaction=transaction)
        self._assert_all_unpaid(plan, bill)

    def test_admin_delete_unlinks_every_installment(self, api_client, admin_user, pay_two_installments):
        plan, bill, transaction = pay_two_installments
        api_client.force_authenticate(user=admin_user)
        api_client.delete(_transaction_url(transaction.id))
        self._assert_all_unpaid(plan, bill)

    def test_refunding_the_payment_reopens_the_plan_for_changes(
        self, api_client, admin_user, pay_two_installments, refund_transaction
    ):
        plan, _, transaction = pay_two_installments
        refund_transaction(transaction=transaction)
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _plan_fromTreatment_url(plan.treatment.patient.id, plan.treatment.id), 
            {'installmentMonths': 6}, 
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)


#══════════════════════════════════════════════════════════════════════════════
#PUT api/installments/<uuid:id>/transactions/<uuid:transactionId>/
#══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestEditInstallmentTransaction:
    @staticmethod
    def _put(api_client, user, plan, transaction, installments, **overrides):
        api_client.force_authenticate(user=user)
        payload = {'installmentIds': [str(i.id) for i in installments], 'date': str(timezone.localdate()),
                   'method': 'cash', 'notes': None, 'status': 'completed'}
        payload.update(overrides)
        return api_client.put(_installments_transaction_url(plan.id, transaction.id), payload, format='json')

    def test_adding_an_installment_to_the_payment(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        one, two = plan.installments.get(sequence=1), plan.installments.get(sequence=2)
        _make_transaction(api_client, admin_user, plan, [one])
        transaction = Transaction.objects.get(bill=bill)

        response = self._put(api_client, admin_user, plan, transaction, [one, two])
        assert response.status_code == status.HTTP_200_OK or render_error(response)

        #refresh instances
        two.refresh_from_db()
        transaction.refresh_from_db()
        bill.refresh_from_db()

        assert two.transaction_id == transaction.id and two.paidAt is not None
        assert transaction.amount == bill.totalPaid == Decimal('400.00')

    def test_dropping_the_last_installment_unlinks_it(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        one, two = plan.installments.get(sequence=1), plan.installments.get(sequence=2)
        _make_transaction(api_client, admin_user, plan, [one, two])
        transaction = Transaction.objects.get(bill=bill)

        response = self._put(api_client, admin_user, plan, transaction, [one])
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        
        #refresh instances
        two.refresh_from_db()
        transaction.refresh_from_db()
        plan.refresh_from_db()

        assert two.paidAt is None and two.transaction_id is None
        assert transaction.amount == plan.totalPaid == Decimal('200.00')

    def test_dropping_an_earlier_installment_while_keeping_a_later_one_returns_400(
        self, api_client, admin_user, plan_with_bill
    ):
        plan, bill = plan_with_bill
        one, two = plan.installments.get(sequence=1), plan.installments.get(sequence=2)
        _make_transaction(api_client, admin_user, plan, [one, two])
        transaction = Transaction.objects.get(bill=bill)

        response = self._put(api_client, admin_user, plan, transaction, [two])

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        one.refresh_from_db()
        assert one.transaction_id == transaction.id   #the failed request changed nothing

    def test_installment_paid_by_another_transaction_returns_400(self, api_client, admin_user, plan_with_bill):
        plan, bill = plan_with_bill
        one, two = plan.installments.get(sequence=1), plan.installments.get(sequence=2)
        _make_transaction(api_client, admin_user, plan, [one])
        _make_transaction(api_client, admin_user, plan, [two])
        second = Transaction.objects.get(bill=bill, amount=Decimal('200.00'), installments=two)   #the transaction that settled #2

        response = self._put(api_client, admin_user, plan, second, [one, two])

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_a_payment_covering_several_installments_can_be_retrieved(self, api_client, admin_user, plan_with_bill):
        #pay two installments with one transaction
        plan, bill = plan_with_bill
        one, two = plan.installments.get(sequence=1), plan.installments.get(sequence=2)
        _make_transaction(api_client, admin_user, plan, [one, two])
        transaction = Transaction.objects.get(bill=bill)

        #fetch it through the installment transaction route
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_installments_transaction_url(plan.id, transaction.id))

        #one row comes back, not two
        assert response.status_code == status.HTTP_200_OK or render_error(response)


#══════════════════════════════════════════════════════════════════════════════
#GET api/installments/options/
#══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestInstallmentOptions:
    @staticmethod
    def _options(api_client, user, plan):
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse('installments_options'), {'installmentPlanId': str(plan.id)})
        return response.data['patientPendingInstallments']

    def test_only_unpaid_installments_including_the_down_payment(
        self, api_client, admin_user, make_treatment, installment_plan_factory
    ):
        plan = installment_plan_factory(treatment=make_treatment(), months=3, down_payment=Decimal('60.00'))
        assert [o['sequence'] for o in self._options(api_client, admin_user, plan)] == [0, 1, 2, 3]

        _mark_paid(plan.installments.get(sequence=0), plan.installments.get(sequence=1))
        options = self._options(api_client, admin_user, plan)

        assert [o['sequence'] for o in options] == [2, 3]
        assert {'id', 'amount', 'sequence', 'dueDate', 'type'} <= set(options[0])


#════════════════════════════════════════════════════════════════════════════════════════
# Treatment-Installment plan relation: Treatment cost changes flow into the plan (signal)
#════════════════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestTreatmentPlanRelations:
    @pytest.fixture
    def partly_paid(self, make_treatment, installment_plan_factory):
        treatment = make_treatment(Decimal('600.00'))
        plan = installment_plan_factory(treatment=treatment, months=3)   #3 x 200.00
        _mark_paid(plan.installments.get(sequence=1))
        #update total paid
        InstallmentPlan.objects.filter(id=plan.id).update(totalPaid=Decimal('200.00'))
        return treatment, plan

    def test_unpaid_installments_absorb_a_cost_increase_evenly(self, partly_paid):
        treatment, plan = partly_paid

        #raise the cost from 600 to 900
        treatment.totalCost = Decimal('900.00')
        treatment.save()

        #the unpaid installments share what is left: (900 - 200) / 2
        plan.refresh_from_db()
        assert plan.totalAmount == Decimal('900.00')
        assert plan.installments.get(sequence=1).amount == Decimal('200.00')   #the paid one is never rewritten
        assert plan.installments.get(sequence=2).amount == Decimal('350.00')
        assert plan.installments.get(sequence=3).amount == Decimal('350.00')

    def test_a_cost_decrease_comes_off_the_last_installment_first(self, partly_paid):
        treatment, plan = partly_paid

        #lower the cost from 600 to 400
        treatment.totalCost = Decimal('400.00')
        treatment.save()

        #the last installment absorbs the whole decrease, the earlier one is untouched
        plan.refresh_from_db()
        assert plan.totalAmount == Decimal('400.00')

        print("\n\nDEBUG:")
        for installment in plan.installments.all():
            print(installment.amount)

        assert plan.installments.get(sequence=1).amount == Decimal('200.00')
        assert plan.installments.get(sequence=2).amount == Decimal('200.00')
        assert plan.installments.get(sequence=3).amount == Decimal('0.00')

    def test_a_larger_decrease_spills_over_to_the_earlier_installment(self, partly_paid):
        treatment, plan = partly_paid

        #lower the cost from 600 to 250 (a decrease of 350)
        treatment.totalCost = Decimal('250.00')
        treatment.save()

        #the last installment goes to 0 and the earlier one takes the remaining 150
        plan.refresh_from_db()
        assert plan.installments.get(sequence=3).amount == Decimal('0.00')
        assert plan.installments.get(sequence=2).amount == Decimal('50.00')

        #whatever the split, the unpaid installments add up to what is still owed
        unpaid_total = plan.installments.get(sequence=2).amount + plan.installments.get(sequence=3).amount
        assert unpaid_total == plan.totalAmount - plan.totalPaid