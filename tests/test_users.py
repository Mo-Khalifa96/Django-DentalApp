import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

#Get user model 
User = get_user_model()


@pytest.fixture
def api_client():
    """Fixture for API client"""
    return APIClient()


@pytest.fixture
def admin_user():
    """Fixture for admin user"""
    return User.objects.create_user(
        email='admin@test.com',
        password='admin123',
        role='admin',
        name='Admin User'
    )

@pytest.fixture
def dentist_user():
    """Fixture for dentist user"""
    return User.objects.create_user(
        email='dentist@test.com',
        password='Dentist123',
        role='dentist',
        name='Dentist User'
    )


@pytest.fixture
def receptionist_user():
    """Fixture for receptionist user"""
    return User.objects.create_user(
        email='receptionist@test.com',
        password='Receptionist123',
        role='receptionist',
        name='Receptionist User'
    )

@pytest.fixture
def assistant_user():
    """Fixture for assistant user"""
    return User.objects.create_user(
        email='assistant@test.com',
        password='Assistant123',
        role='assistant',
        name='Assistant User'
    )

@pytest.mark.django_db
class TestUpdateUserAPIView:
    def test_admin_can_update_user_with_role_and_permissions(self, api_client, admin_user, receptionist_user):
        """Admin should be able to update role, permissions, and password of another user."""
        api_client.force_authenticate(user=admin_user)
        
        url = reverse("retrieve_update_delete_user", kwargs={"id": receptionist_user.id})
        payload = {
            "name": "Updated Receptionist",
            "email": "updated_receptionist@test.com",
            "role": "Dentist",  #Admin can change role
            "permissions": {
                'view.patients': True,
                'view.patientDetail': True,
                'create.patient': True,
                'update.patient': True,
                'delete.patient': False,  #default 
                'view.visits': True,
                'create.visit': True,
            }
        }

        response = api_client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        receptionist_user.refresh_from_db()
        assert receptionist_user.name == "Updated Receptionist"
        assert receptionist_user.email == "updated_receptionist@test.com"
        assert receptionist_user.role == "dentist"
        assert 'view.patientDetail' in receptionist_user.userPermissions
        assert 'create.visit' in receptionist_user.userPermissions
        assert 'delete.patient' not in receptionist_user.userPermissions

    @pytest.mark.django_db
    def test_non_admin_cannot_update_role_and_permissions(self, api_client, receptionist_user):
        """Non-admin cannot change their role or permissions even if sent in payload."""
        api_client.force_authenticate(user=receptionist_user)
        original_role = receptionist_user.role
        original_permissions = list(receptionist_user.userPermissions)

        url = reverse("retrieve_update_delete_user", kwargs={"id": receptionist_user.id})
        payload = {
            "name": "Updated Name",
            "role": "Admin",
            "permissions": {
                'view.patients': True,
                'view.patientDetail': True,
            }
        }

        response = api_client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        receptionist_user.refresh_from_db()
        assert receptionist_user.name == "Updated Name"  # name update went through
        assert receptionist_user.role == original_role   #Role unchanged for non-admins
        assert receptionist_user.userPermissions == original_permissions  #Permissions unchanged for non-admins

    def test_password_update_hashes_properly(self, api_client, receptionist_user):
        """Ensure password updates are hashed and not stored raw."""
        api_client.force_authenticate(user=receptionist_user)

        url = reverse("retrieve_update_delete_user", kwargs={"id": receptionist_user.id})
        payload = {"currentPassword": "Receptionist123", 
                   "newPassword": "Strongpass123",
                   "newPassword2": "Strongpass123"}

        response = api_client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        receptionist_user.refresh_from_db()
        assert check_password("Strongpass123", receptionist_user.password)


    def test_permission_enforcement_blocks_non_privileged_user(self, api_client, receptionist_user, assistant_user):
        """Receptionist should get 403 if they try to delete another user (because they lack permission)."""
        api_client.force_authenticate(user=receptionist_user)

        url = reverse("retrieve_update_delete_user", kwargs={"id": assistant_user.id})

        response = api_client.delete(url, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
