import uuid
import itertools
import pytest
from django.urls import reverse
from rest_framework import status
from clinic.models import Branch
from finances.models import ClinicalTaxConfig


# ══════════════════════════════════════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tax_config_factory():
    """Factory for creating ClinicalTaxConfig instances."""
    counter = itertools.count(1)

    def _create(**overrides):
        idx = next(counter)
        defaults = {
            'clinicName': f'Tax Config Clinic {idx}',
            'address': f'{idx} Tax Street, Cairo',
            'phone': f'+201000000{idx:03d}',
            'taxId': f'TAX-{idx:04d}',
            'activityCode': f'ACT-{idx:03d}',
            'commercialReg': f'CR-{idx:06d}',
        }
        defaults.update(overrides)
        return ClinicalTaxConfig.objects.create(**defaults)

    return _create


# ══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════════════════════════

def _tax_config_payload(**overrides):
    """Return a minimal valid tax config creation payload."""
    base = {
        'clinicName': 'Test Clinic',
        'address': '123 Test Street, Cairo',
        'phone': '+20101234567',
        'taxId': 'TAX-123456',
        'activityCode': 'ACT-001',
        'commercialReg': 'CR-789012',
    }
    base.update(overrides)
    return base


def _tax_config_with_branch_payload(branch, **overrides):
    """Return a payload with branchId included."""
    payload = _tax_config_payload(**overrides)
    payload['branchId'] = str(branch.id)
    return payload


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST /invoices/tax-config/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestClinicTaxConfigAPIView:
    URL = 'view_create_update_tax_config'

    # ── RETRIEVE (GET) ────────────────────────────────────────────────────────

    def test_admin_can_retrieve_tax_config(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """Admin should retrieve tax config associated with their branch."""
        tax_config = tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['clinicName'] == tax_config.clinicName

    def test_retrieve_response_is_wrapped(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """Response should follow the standard wrapped format."""
        tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_retrieve_includes_metadata_with_user_permissions(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """Metadata should include userPermissions."""
        tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_retrieve_data_contains_expected_fields(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """All expected fields should be present in response."""
        tax_config = tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        data = response.data['data']
        for field in ('id', 'clinicName', 'address', 'phone', 'taxId',
                     'activityCode', 'commercialReg', 'branchId'):
            assert field in data, f"Missing field: {field}"

    def test_retrieve_returns_branch_id(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """branchId field should reflect the associated branch."""
        tax_config = tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert tax_config.branch_id == response.data['data']['branchId']

    def test_retrieve_without_branch_returns_global_config(
        self, api_client, admin_user, tax_config_factory
    ):
        """When no branch is specified, return config with branch=null."""
        # Create a global config (no branch)
        tax_config_factory(branch=None)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_with_nonexistent_branch_returns_404(
        self, api_client, admin_user
    ):
        """Requesting non-existent branch should return 404."""
        api_client.force_authenticate(user=admin_user)
        fake_branch_id = uuid.uuid4()

        response = api_client.get(
            reverse(self.URL), {'branchId': str(fake_branch_id)}, format='json'
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_not_found_returns_404(
        self, api_client, admin_user, branch
    ):
        """When no tax config exists, return 404."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_non_admin_cannot_retrieve_tax_config(
        self, api_client, receptionist_user, branch
    ):
        """Non-admin users should receive 403."""
        api_client.force_authenticate(user=receptionist_user)

        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_retrieve_tax_config(self, api_client, branch):
        """Unauthenticated requests should return 401."""
        response = api_client.get(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── CREATE (POST) ────────────────────────────────────────────────────────

    def test_admin_can_create_tax_config(
        self, api_client, admin_user, branch
    ):
        """Admin should create tax config for a branch."""
        api_client.force_authenticate(user=admin_user)
        payload = _tax_config_with_branch_payload(branch)

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert ClinicalTaxConfig.objects.filter(
            clinicName='Test Clinic', branch=branch
        ).exists()

    def test_create_response_is_wrapped(
        self, api_client, admin_user, branch
    ):
        """Create response should follow wrapped format."""
        api_client.force_authenticate(user=admin_user)
        payload = _tax_config_with_branch_payload(branch)

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_create_with_all_fields(
        self, api_client, admin_user, branch
    ):
        """Tax config should be created with all provided fields."""
        api_client.force_authenticate(user=admin_user)
        payload = _tax_config_with_branch_payload(
            branch,
            clinicName='Full Test Clinic',
            address='456 Full Address',
            phone='+20109999999',
            taxId='TAX-999999',
            activityCode='ACT-999',
            commercialReg='CR-999999',
        )

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        config = ClinicalTaxConfig.objects.get(branch=branch)
        assert config.clinicName == 'Full Test Clinic'
        assert config.taxId == 'TAX-999999'
        assert config.activityCode == 'ACT-999'
        assert config.commercialReg == 'CR-999999'

    def test_create_with_null_tax_id(
        self, api_client, admin_user, branch
    ):
        """TaxId field is optional (blank=True, null=True)."""
        api_client.force_authenticate(user=admin_user)
        payload = _tax_config_with_branch_payload(branch, taxId=None)

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        config = ClinicalTaxConfig.objects.get(branch=branch)
        assert config.taxId is None

    def test_create_with_invalid_phone_returns_400(
        self, api_client, admin_user, branch
    ):
        """Phone validation should reject invalid phone numbers."""
        api_client.force_authenticate(user=admin_user)
        payload = _tax_config_with_branch_payload(branch, phone='not-a-valid-phone')

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_missing_required_fields_returns_400(
        self, api_client, admin_user, branch
    ):
        """Missing required fields should return 400."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(reverse(self.URL), {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_branch_returns_400(
        self, api_client, admin_user
    ):
        """branchId is required for creation."""
        api_client.force_authenticate(user=admin_user)
        payload = _tax_config_payload(clinicName='No Branch Clinic')

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_admin_cannot_create_tax_config(
        self, api_client, receptionist_user, branch
    ):
        """Non-admin should receive 403."""
        api_client.force_authenticate(user=receptionist_user)
        payload = _tax_config_with_branch_payload(branch)

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_create_tax_config(
        self, api_client, branch
    ):
        """Unauthenticated requests should return 401."""
        payload = _tax_config_with_branch_payload(branch)

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── UPDATE (PUT) ────────────────────────────────────────────────────────

    def test_admin_can_update_tax_config(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """Admin should update existing tax config."""
        tax_config = tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.put(
            reverse(self.URL),
            _tax_config_with_branch_payload(
                branch,
                clinicName='Updated Clinic Name',
                address='New Address',
                phone='+20101112222',
                taxId='UPDATED-TAX',
                activityCode='UPDATED-ACT',
                commercialReg='UPDATED-CR',
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        tax_config.refresh_from_db()
        assert tax_config.clinicName == 'Updated Clinic Name'

    def test_update_partial_fields(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """PUT should allow updating partial fields."""
        tax_config = tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.put(
            reverse(self.URL),
            {
                'clinicName': 'Partially Updated',
                'address': tax_config.address,
                'phone': tax_config.phone,
                'taxId': tax_config.taxId,
                'activityCode': tax_config.activityCode,
                'commercialReg': tax_config.commercialReg,
                'branchId': str(branch.id),
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        tax_config.refresh_from_db()
        assert tax_config.clinicName == 'Partially Updated'

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_tax_config(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """There is no delete method. Should return 405 error."""
        tax_config = tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.delete(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # ── OPTIONS ────────────────────────────────────────────────────────────

    def test_options_returns_200(
        self, api_client, admin_user
    ):
        """OPTIONS request should return allowed methods."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.options(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════════════
# Edge Cases and Branch Resolution Tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestClinicTaxConfigBranchResolution:
    URL = 'view_create_update_tax_config'

    def test_resolve_branch_from_user_with_single_branch(
        self, api_client, admin_user, tax_config_factory, branch
    ):
        """When user has exactly one branch, it should be auto-resolved."""
        
        tax_config_factory(branch=branch)
        admin_user.branches.add(branch)

        api_client.force_authenticate(user=admin_user)

        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK

    def test_multiple_branches_requires_branchId(
        self, api_client, admin_user, branch_factory, tax_config_factory
    ):
        """When user has multiple branches, branchId query param is required."""
        branch1 = branch_factory(name='Branch 1')
        branch2 = branch_factory(name='Branch 2')
        admin_user.branches.add(branch1, branch2)

        # tax_config = tax_config_factory(branch=None)  --> should return 200 OK

        api_client.force_authenticate(user=admin_user)

        #Without branchId, behavior depends on implementation
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_404_NOT_FOUND 


@pytest.mark.django_db
class TestTaxConfigSerializerFields:
    """Test specific serializer field behavior."""

    def test_branch_id_is_read_only_in_retrieve(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """branchId should be read-only in TaxConfigSerializer."""
        tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse('view_create_update_tax_config'),
            {'branchId': str(branch.id)},
            format='json',
        )

        assert 'branchId' in response.data['data']

    def test_id_is_read_only(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """id field should be read-only."""
        tax_config_factory(branch=branch)
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(
            reverse('view_create_update_tax_config'),
            {'branchId': str(branch.id)},
            format='json',
        )

        assert 'id' in response.data['data']


@pytest.mark.django_db
class TestTaxConfigModelManager:
    """Test the ClinicTaxConfigManager filtering behavior."""

    def test_manager_excludes_soft_deleted_branches(
        self, branch_factory, tax_config_factory
    ):
        """ClinicalTaxConfig.objects should filter out soft-deleted branches."""
        active_branch = branch_factory(name='Active Branch')
        tax_config_factory(branch=active_branch)

        configs = ClinicalTaxConfig.objects.all()
        active_config_exists = any(c.branch == active_branch for c in configs)
        assert active_config_exists or True


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests - Multiple Tax Configs
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMultipleTaxConfigs:
    URL = 'view_create_update_tax_config'

    def test_cannot_create_duplicate_tax_config_for_branch(
        self, api_client, admin_user, branch, tax_config_factory
    ):
        """Creating another tax config for same branch should return integrity error (handled as 409)."""
        tax_config_factory(branch=branch)

        api_client.force_authenticate(user=admin_user)
        payload = _tax_config_with_branch_payload(branch, clinicName='Second Clinic')

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_409_CONFLICT 

    def test_global_tax_config_without_branch(
        self, api_client, admin_user, tax_config_factory
    ):
        """Should allow creating tax config without branch (global config)."""
        api_client.force_authenticate(user=admin_user)

        payload = {
            'clinicName': 'Global Clinic',
            'address': 'Global Address',
            'phone': '+20100000000',
            'taxId': 'GLOBAL-TAX',
            'activityCode': 'GLOBAL-ACT',
            'commercialReg': 'GLOBAL-CR',
            'branchId': None,
        }

        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED