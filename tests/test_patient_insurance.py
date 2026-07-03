import uuid
import pytest
from datetime import date
from decimal import Decimal
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from patients.models import PatientCoverage
from finances.models import InsuranceProvider


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def coverage_factory(patient_factory):
    '''Returns the PatientCoverage instance auto-created by Patient.save().'''

    def _create(**kwargs):
        patient = kwargs.pop('patient', None) or patient_factory(**kwargs)
        return PatientCoverage.objects.get(patient=patient)

    return _create


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _coverage_url(patient_id):
    return reverse('create_retrieve_update_coverage', kwargs={'patientId': patient_id})

def _fill_payload(provider, **overrides):
    '''Minimal valid POST payload for filling in a blank coverage instance.'''

    base = {
        'providerId':        str(provider.id),
        'memberId':          'MEM-001',
        'annualMax':         '10000.00',
        'effectiveFrom':     str(date.today().replace(month=1, day=1)),
        'effectiveTo':       str(date.today().replace(month=12, day=31)),
        'eligibilityStatus': 'active',
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET  /insurance/coverage/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListPatientCoveragePlansAPIView:
    LIST_URL = 'list_patient_coverages'

    def test_admin_lists_all_coverages(
        self, api_client, admin_user, coverage_factory
    ):
        c1 = coverage_factory()
        c2 = coverage_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(c1.id) in ids
        assert str(c2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, coverage_factory
    ):
        coverage_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True or render_error(response)
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f'Missing key: {key}'

    def test_dentist_sees_only_own_patients_coverages(
        self, api_client, dentist_user, other_dentist_user, coverage_factory
    ):
        c_own   = coverage_factory(doctor=dentist_user)
        c_other = coverage_factory(doctor=other_dentist_user)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(c_own.id) in ids or render_error(response)
        assert str(c_other.id) not in ids or render_error(response)

    def test_receptionist_sees_branch_filtered_coverages(
        self, api_client, receptionist_user, coverage_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        receptionist_user.branches.set([b1])

        c_own   = coverage_factory(branch=b1)
        c_other = coverage_factory(branch=b2)

        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(c_own.id) in ids or render_error(response)
        assert str(c_other.id) not in ids or render_error(response)

    def test_coverages_of_soft_deleted_patients_excluded(
        self, api_client, admin_user, coverage_factory
    ):
        coverage = coverage_factory()
        patient  = coverage.patient
        patient.is_deleted = True
        patient.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(coverage.id) not in [i['id'] for i in response.data['data']] or render_error(response)

    def test_assistant_cannot_list_coverages(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_list_coverages(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /insurance/coverage/<patientId>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrievePatientCoverageAPIView:

    def test_admin_retrieves_blank_instance_for_new_patient(
        self, api_client, admin_user, coverage_factory
    ):
        '''Every patient auto-generates a blank coverage instance on creation.
        GET retrieves that instance immediately — no POST needed first.'''

        coverage = coverage_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_coverage_url(coverage.patient.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['id'] == str(coverage.id)

    def test_retrieve_response_is_wrapped_with_metadata(
        self, api_client, admin_user, coverage_factory
    ):
        '''RetrieveUpdatePatientCoverageSerializer inherits UserPermissionsMixin.'''
        
        coverage = coverage_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_coverage_url(coverage.patient.id))

        assert response.data.get('success') is True or render_error(response)
        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_updated_at_hidden_for_fresh_unmodified_instance(
        self, api_client, admin_user, coverage_factory
    ):
        coverage = coverage_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_coverage_url(coverage.patient.id))

        assert response.data['data']['updatedAt'] is None or render_error(response)

    def test_dentist_cannot_retrieve_another_dentists_patients_coverage(
        self, api_client, dentist_user, other_dentist_user, coverage_factory
    ):
        coverage = coverage_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_coverage_url(coverage.patient.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_retrieve_coverage(self, api_client, coverage_factory):
        coverage = coverage_factory()
        response = api_client.get(_coverage_url(coverage.patient.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)
        


# ══════════════════════════════════════════════════════════════════════════════
# POST  /insurance/coverage/<patientId>/   (fills in the auto-created instance)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFillInPatientCoverageAPIView:
    def test_admin_fills_in_coverage_with_existing_provider(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id),
            _fill_payload(provider),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        coverage.refresh_from_db()
        assert coverage.provider == provider
        assert coverage.memberId == 'MEM-001'
        assert coverage.eligibilityStatus == 'active'

    def test_fill_in_captures_provider_name_snapshot(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory(name='BlueCross Health')
        coverage = coverage_factory()

        api_client.force_authenticate(user=admin_user)
        api_client.post(
            _coverage_url(coverage.patient.id), _fill_payload(provider), format='json'
        )
        coverage.refresh_from_db()
        assert coverage.providerName == 'BlueCross Health'

    def test_fill_in_inherits_annual_max_from_provider_when_omitted(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory(annualMax=Decimal('8000.00'))
        coverage = coverage_factory()

        payload = _fill_payload(provider)
        payload['annualMax'] = None

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), payload, format='json'
        )
        coverage.refresh_from_db()
        assert coverage.annualMax == Decimal('8000.00') or render_error(response)

    def test_fill_in_with_inline_new_provider_creates_and_assigns_provider(
        self, api_client, admin_user, coverage_factory
    ):
        '''is_newProvider=True + newProviderDetails creates a new InsuranceProvider
        and assigns it to the coverage atomically. contact is now included in'''

        coverage = coverage_factory()
        payload = {
            'is_newProvider': True,
            'newProviderDetails': {
                'name':            'Inline New Insurer',
                'tier':            'corporate',
                'coveragePercent': 75,
            },
            'memberId':          'MEM-NEW',
            'annualMax':         '6000.00',
            'effectiveFrom':     str(date.today().replace(month=1, day=1)),
            'effectiveTo':       str(date.today().replace(month=12, day=31)),
            'eligibilityStatus': 'active',
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), payload, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        provider = InsuranceProvider.objects.get(name='Inline New Insurer')
        coverage.refresh_from_db()
        assert coverage.provider == provider

    def test_cannot_provide_both_provider_id_and_is_new_provider(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        payload  = _fill_payload(
            provider,
            is_newProvider=True,
            newProviderDetails={'name': 'Conflict', 'tier': 'direct',
                                'contact': 'x@x.com', 'coveragePercent': 50},
        )
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), payload, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_no_provider_and_no_new_provider_details_returns_400(
        self, api_client, admin_user, coverage_factory
    ):
        coverage = coverage_factory()
        payload = {
            'memberId':          'MEM-NOPROVIDER',
            'annualMax':         '5000.00',
            'effectiveFrom':     str(date.today().replace(month=1, day=1)),
            'effectiveTo':       str(date.today().replace(month=12, day=31)),
            'eligibilityStatus': 'active',
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), payload, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_member_id_is_required(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        payload  = _fill_payload(provider)
        payload.pop('memberId')
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), payload, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_eligibility_status_is_required(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        payload  = _fill_payload(provider)
        payload.pop('eligibilityStatus')
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), payload, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_fill_in_response_is_wrapped(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), _fill_payload(provider), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_receptionist_can_fill_in_coverage(
        self, api_client, receptionist_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), _fill_payload(provider), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_assistant_cannot_fill_in_coverage(
        self, api_client, assistant_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            _coverage_url(coverage.patient.id), _fill_payload(provider), format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_fill_in_coverage(
        self, api_client, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        response = api_client.post(
            _coverage_url(coverage.patient.id), _fill_payload(provider), format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# PATCH | PUT  /insurance/coverage/<patientId>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUpdatePatientCoverageAPIView:

    def test_admin_can_patch_eligibility_status(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        coverage.provider          = provider
        coverage.memberId          = 'MEM-PATCH'
        coverage.eligibilityStatus = 'active'
        coverage.save()

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'eligibilityStatus': 'expired'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        coverage.refresh_from_db()
        assert coverage.eligibilityStatus == 'expired'

    def test_patch_does_not_require_all_fields(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        coverage = coverage_factory()
        coverage.provider = provider
        coverage.memberId = 'KEEP-ME'
        coverage.save()

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'deductibleMet': True},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        coverage.refresh_from_db()
        assert coverage.deductibleMet is True
        assert coverage.memberId == 'KEEP-ME'   # unchanged

    def test_put_requires_member_id_annual_max_dates_and_status(
        self, api_client, admin_user, coverage_factory
    ):
        coverage = coverage_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _coverage_url(coverage.patient.id),
            {'eligibilityStatus': 'active'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_setting_provider_to_null_clears_all_coverage_fields(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        '''validate(): sending providerId=null explicitly removes the insurer 
        and sets all COVERAGE_FIELDS to None.'''

        provider = insurance_provider_factory()
        coverage = coverage_factory()
        coverage.provider          = provider
        coverage.memberId          = 'TO-CLEAR'
        coverage.eligibilityStatus = 'active'
        coverage.annualMax         = Decimal('5000.00')
        coverage.effectiveFrom     = date.today().replace(month=1, day=1)
        coverage.effectiveTo       = date.today().replace(month=12, day=31)
        coverage.save()

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'providerId': None},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        coverage.refresh_from_db()
        assert coverage.provider is None
        assert coverage.memberId is None
        assert coverage.annualMax is None

    def test_switching_provider_clears_stale_fields_from_old_insurer(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        '''validate(): when provider changes, all COVERAGE_FIELDS are cleared
        before the new provider's values apply — prevents old insurer's data
        bleeding into the new record.'''
        
        old_provider = insurance_provider_factory(name='Old Insurer')
        new_provider = insurance_provider_factory(name='New Insurer')
        coverage     = coverage_factory()
        coverage.provider          = old_provider
        coverage.memberId          = 'OLD-MEM'
        coverage.eligibilityStatus = 'active'
        coverage.save()

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _coverage_url(coverage.patient.id),
            {'providerId': str(new_provider.id)},
            format='json',
        )
        coverage.refresh_from_db()
        assert coverage.provider == new_provider
        assert coverage.memberId is None   # cleared by validate()

    def test_update_with_inline_new_provider_creates_and_reassigns(
        self, api_client, admin_user, coverage_factory, insurance_provider_factory
    ):
        old_provider = insurance_provider_factory(name='Old Insurer')
        coverage     = coverage_factory()
        coverage.provider = old_provider
        coverage.save()

        payload = {
            'is_newProvider': True,
            'newProviderDetails': {
                'name':            'Brand New Co',
                'tier':            'universal',
                'contact':         'new@brand.com',
                'coveragePercent': 90,
            },
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id), payload, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        coverage.refresh_from_db()
        assert coverage.provider.name == 'Brand New Co'

    def test_update_response_is_wrapped(
        self, api_client, admin_user, coverage_factory
    ):
        coverage = coverage_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'eligibilityStatus': 'expired'},
            format='json',
        )
        assert response.data.get('success') is True or render_error(response)
        assert 'data' in response.data

    def test_receptionist_can_update_coverage(
        self, api_client, receptionist_user, coverage_factory
    ):
        coverage = coverage_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'eligibilityStatus': 'expired'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_other_dentist_cannot_update_coverage(
        self, api_client, dentist_user, other_dentist_user, coverage_factory
    ):
        '''PatientDataPermissions: dentist must be the patient's current doctor.'''

        coverage = coverage_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'eligibilityStatus': 'expired'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_assistant_cannot_update_coverage(
        self, api_client, assistant_user, coverage_factory
    ):
        coverage = coverage_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'eligibilityStatus': 'expired'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_update_coverage(self, api_client, coverage_factory):
        coverage = coverage_factory()
        response = api_client.patch(
            _coverage_url(coverage.patient.id),
            {'eligibilityStatus': 'expired'},
            format='json',
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# Signal: post_save Transaction → usedYTD
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUsedYTDSignal:
    def test_insurance_transaction_sets_used_ytd(
        self, dentist_user, patient_factory, bill_factory
    ):
        from finances.models import Transaction

        patient  = patient_factory(doctor=dentist_user)
        coverage = PatientCoverage.objects.get(patient=patient)
        bill     = bill_factory(patient=patient)

        Transaction.objects.create(
            bill=bill, patient=patient, visit=bill.visits.first(),
            date=date.today(), amount=Decimal('500.00'), method='insurance',
        )
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('500.00')

    def test_multiple_insurance_transactions_accumulate_in_used_ytd(
        self, dentist_user, patient_factory, bill_factory
    ):
        from finances.models import Transaction

        patient  = patient_factory(doctor=dentist_user)
        coverage = PatientCoverage.objects.get(patient=patient)
        bill     = bill_factory(patient=patient)
        visit    = bill.visits.first()

        Transaction.objects.create(
            bill=bill, patient=patient, visit=visit,
            date=date.today(), amount=Decimal('200.00'), method='insurance',
        )
        Transaction.objects.create(
            bill=bill, patient=patient, visit=visit,
            date=date.today(), amount=Decimal('300.00'), method='insurance',
        )
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('500.00')

    def test_cash_transaction_does_not_affect_used_ytd(
        self, dentist_user, patient_factory, bill_factory
    ):
        from finances.models import Transaction

        patient  = patient_factory(doctor=dentist_user)
        coverage = PatientCoverage.objects.get(patient=patient)
        bill     = bill_factory(patient=patient)

        Transaction.objects.create(
            bill=bill, patient=patient, visit=bill.visits.first(),
            date=date.today(), amount=Decimal('500.00'), method='cash',
        )
        coverage.refresh_from_db()
        assert coverage.usedYTD is None   # never touched

    def test_changing_method_from_insurance_to_cash_recalculates_ytd(
        self, dentist_user, patient_factory, bill_factory
    ):
        '''pre_save captures _prev_method. When a transaction changes FROM
        'insurance' to another method, the signal recalculates usedYTD,
        correctly excluding the now-non-insurance transaction.'''

        from finances.models import Transaction

        patient  = patient_factory(doctor=dentist_user)
        coverage = PatientCoverage.objects.get(patient=patient)
        bill     = bill_factory(patient=patient)

        txn = Transaction.objects.create(
            bill=bill, patient=patient, visit=bill.visits.first(),
            date=date.today(), amount=Decimal('300.00'), method='insurance',
        )
        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('300.00')

        txn.method = 'cash'
        txn.save(update_fields=['method'])

        coverage.refresh_from_db()
        assert coverage.usedYTD == Decimal('0.00')


# ══════════════════════════════════════════════════════════════════════════════
# GET  /insurance/coverage/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrievePatientCoverageOptionsAPIView:
    URL = 'patient_coverage_options'

    def test_authenticated_user_gets_all_option_keys(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'patientChoices',
                    'insuranceProviderChoices', 'eligibilityStatusChoices'):
            assert key in response.data, f'Missing key: {key}'

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'success' not in response.data or render_error(response)

    def test_eligibility_status_choices_cover_all_statuses(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['eligibilityStatusChoices']}
        expected = {c.value for c in PatientCoverage.EligibilityStatusChoices}
        assert returned == expected or render_error(response)

    def test_patient_choices_empty_when_branches_exist_and_no_filters(
        self, api_client, admin_user, patient_factory, branch_factory
    ):
        branch_factory()
        patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['patientChoices'] == [] or render_error(response)

    def test_patient_choices_filtered_by_branch_id(
        self, api_client, admin_user, patient_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        p1 = patient_factory(branch=b1)
        p2 = patient_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p1.id) in ids or render_error(response)
        assert str(p2.id) not in ids or render_error(response)

    def test_patient_choices_filtered_by_doctor_id(
        self, api_client, admin_user, patient_factory, dentist_user, branch_factory
    ):
        branch_factory()   # ensure branches exist so default guard activates
        p_own   = patient_factory(doctor=dentist_user)
        p_other = patient_factory()

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'doctorId': str(dentist_user.id)})

        ids = {str(c['patientId']) for c in response.data['patientChoices']}
        assert str(p_own.id) in ids or render_error(response)
        assert str(p_other.id) not in ids or render_error(response)

    def test_provider_choices_empty_when_branches_exist_and_no_branch_id(
        self, api_client, admin_user, insurance_provider_factory, branch_factory
    ):
        b = branch_factory()
        insurance_provider_factory(branch=b)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['insuranceProviderChoices'] == [] or render_error(response)

    def test_provider_choices_filtered_by_branch_id(
        self, api_client, admin_user, insurance_provider_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        pr1 = insurance_provider_factory(branch=b1)
        pr2 = insurance_provider_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b1.id)})

        ids = {str(c['providerId']) for c in response.data['insuranceProviderChoices']}
        assert str(pr1.id) in ids or render_error(response)
        assert str(pr2.id) not in ids or render_error(response)

    def test_invalid_doctor_id_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'doctorId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_non_admin_can_access_options(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

