import uuid
import pytest
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from finances.models import InsuranceProvider


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detail_url(provider_id):
    return reverse('retrieve_update_delete_provider', kwargs={'providerId': provider_id})

def _create_payload(**overrides):
    base = {
        'name':            'Test Provider',
        'tier':             'direct',
        'contact':          'billing@testprovider.com',
        'coveragePercent':  75,
        'currency':         '$',
        'branchId':         None,
    }
    base.update(overrides)
    return base

def _grant(user, permission):
    user.userPermissions.append(permission)
    user.save(update_fields=['userPermissions'])


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /insurance/providers/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateInsuranceProvidersAPIView:
    LIST_URL = 'list_create_providers'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_providers(
        self, api_client, admin_user, insurance_provider_factory
    ):
        p1 = insurance_provider_factory(name='Provider A')
        p2 = insurance_provider_factory(name='Provider B')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(p1.id) in ids
        assert str(p2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, insurance_provider_factory
    ):
        insurance_provider_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.data['success'] is True or render_error(response)
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f'Missing key: {key}'

    def test_user_with_permission_sees_branch_filtered_providers(
        self, api_client, user_factory, insurance_provider_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        user = user_factory(role='accountant')
        user.branches.set([b1])
        _grant(user, 'view.insuranceProviders')

        p_own   = insurance_provider_factory(branch=b1)
        p_other = insurance_provider_factory(branch=b2)

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(p_own.id) in ids
        assert str(p_other.id) not in ids

    def test_providers_with_soft_deleted_branch_excluded(
        self, api_client, admin_user, insurance_provider_factory, branch_factory
    ):
        '''InsuranceProviderManager: Q(branch__is_deleted=False) hides stale entries.'''

        active = branch_factory()
        dying  = branch_factory()
        visible = insurance_provider_factory(branch=active)
        hidden  = insurance_provider_factory(branch=dying)

        dying.is_deleted = True
        dying.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    def test_provider_with_null_branch_always_visible(
        self, api_client, admin_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory(branch=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert str(provider.id) in [i['id'] for i in response.data['data']]

    def test_list_supports_search_by_name(
        self, api_client, admin_user, insurance_provider_factory
    ):
        visible = insurance_provider_factory(name='United Health')
        insurance_provider_factory(name='National Bank Insurance')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL), {'search': 'united'})

        assert str(visible.id) in [i['id'] for i in response.data['data']]

    def test_assistant_cannot_list_providers(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_list_providers(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_provider(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert InsuranceProvider.objects.filter(name='Test Provider').exists()

    def test_create_response_is_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )
        assert response.data.get('success') is True or render_error(response)
        assert 'data' in response.data

    def test_create_requires_coverage_percent(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        payload = _create_payload()
        payload.pop('coveragePercent')
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_requires_tier(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        payload = _create_payload()
        payload.pop('tier')
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_invalid_tier_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(tier='not_a_real_tier'),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_negative_coverage_percent_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(coveragePercent=-10),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_coverage_percent_over_100_is_unacceptible(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(coveragePercent=150),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_without_branch_id_key_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        payload = _create_payload()
        payload.pop('branchId')
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_explicit_branch(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(branchId=str(branch.id)),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        provider = InsuranceProvider.objects.get(name='Test Provider')
        assert provider.branch == branch

    def test_user_with_create_permission_can_create_provider(
        self, api_client, user_factory
    ):
        user = user_factory(role='accountant')
        _grant(user, 'create.insuranceProvider')
        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_assistant_cannot_create_provider(self, api_client, assistant_user):
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_create_provider(self, api_client):
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | PATCH | DELETE  /insurance/providers/<providerId>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteInsuranceProviderAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_provider(
        self, api_client, admin_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(provider.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['id'] == str(provider.id)

    def test_retrieve_response_includes_metadata(
        self, api_client, admin_user, insurance_provider_factory
    ):
        '''RetrieveUpdateDeleteInsuranceProviderSerializer inherits UserPermissionsMixin.'''

        provider = insurance_provider_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(provider.id))

        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_user_cannot_retrieve_provider_with_soft_deleted_branch(
        self, api_client, admin_user, insurance_provider_factory, branch_factory
    ):
        dying = branch_factory()
        provider = insurance_provider_factory(branch=dying)
        dying.is_deleted = True
        dying.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(provider.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_nonexistent_provider_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_detail_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_unauthenticated_cannot_retrieve_provider(
        self, api_client, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        response = api_client.get(_detail_url(provider.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_assistant_cannot_retrieve_provider(
        self, api_client, assistant_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(_detail_url(provider.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    # ── UPDATE ────────────────────────────────────────────────────────────────

    def test_admin_can_update_provider(
        self, api_client, admin_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory(coveragePercent=70)
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(provider.id), {'coveragePercent': 90}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        provider.refresh_from_db()
        assert provider.coveragePercent == 90

    def test_branch_id_is_read_only_on_update(
        self, api_client, admin_user, insurance_provider_factory, branch_factory
    ):
        original = branch_factory()
        new_branch = branch_factory()
        provider = insurance_provider_factory(branch=original)

        api_client.force_authenticate(user=admin_user)
        api_client.patch(
            _detail_url(provider.id), {'branchId': str(new_branch.id)}, format='json'
        )
        provider.refresh_from_db()
        assert provider.branch == original

    def test_update_with_invalid_tier_returns_400(
        self, api_client, admin_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(provider.id), {'tier': 'bogus'}, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_update_response_is_wrapped(
        self, api_client, admin_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _detail_url(provider.id), {'notes': 'Renewed contract'}, format='json'
        )
        assert response.data.get('success') is True or render_error(response)
        assert 'data' in response.data

    def test_receptionist_cannot_update_provider(
        self, api_client, receptionist_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.patch(
            _detail_url(provider.id), {'notes': 'Hijacked'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_update_provider(
        self, api_client, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        response = api_client.patch(
            _detail_url(provider.id), {'notes': 'Hijacked'}, format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_provider(
        self, api_client, admin_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        pid = provider.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_detail_url(pid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not InsuranceProvider.objects.filter(id=pid).exists()

    def test_delete_is_hard_delete(
        self, api_client, admin_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        pid = provider.id
        api_client.force_authenticate(user=admin_user)
        api_client.delete(_detail_url(pid))
        assert not InsuranceProvider.all_objects.filter(id=pid).exists()

    def test_receptionist_cannot_delete_provider(
        self, api_client, receptionist_user, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.delete(_detail_url(provider.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_delete_provider(
        self, api_client, insurance_provider_factory
    ):
        provider = insurance_provider_factory()
        response = api_client.delete(_detail_url(provider.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_delete_nonexistent_provider_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_detail_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /insurance/providers/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveInsuranceProvidersOptionsAPIView:
    URL = 'providers_options'

    def test_authenticated_user_gets_options(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'branchChoices' in response.data
        assert 'tierChoices' in response.data

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'success' not in response.data or render_error(response)

    def test_tier_choices_cover_all_tiers(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['tierChoices']}
        expected = {c.value for c in InsuranceProvider.InuranceTierChoices}
        assert returned == expected or render_error(response)

    def test_branch_choices_reflect_existing_branches(
        self, api_client, admin_user, branch_factory
    ):
        b1 = branch_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        ids = {str(c['branchId']) for c in response.data['branchChoices']}
        assert str(b1.id) in ids or render_error(response)

    def test_non_admin_can_access_options(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_200_OK or render_error(response)

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)
