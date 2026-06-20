import uuid
import pytest
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /users/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateUserAPIView:
    URL = 'list_create_users'

    # ── helpers ───────────────────────────────────────────────────────────────

    def _payload(self, **overrides):
        base = {
            'email': 'newuser@test.com',
            'name': 'New User',
            'role': 'receptionist',
            'password': 'Strongpass123!',
            'password2': 'Strongpass123!',
        }
        base.update(overrides)
        return base

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_users(self, api_client, admin_user, dentist_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(user['id']) for user in response.data['data']]
        assert str(dentist_user.id) in ids

    def test_list_response_excludes_soft_deleted_users(
        self, api_client, admin_user, receptionist_user
    ):
        """Soft-deleted users must not appear in the list."""
        receptionist_user.is_deleted = True
        receptionist_user.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [str(user['id']) for user in response.data['data']]
        assert str(receptionist_user.id) not in ids

    def test_non_admin_cannot_list_users(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_list_users(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_user_when_no_branch_exists(self, api_client, admin_user):
        """When no Branch rows exist the branchIds validation is skipped."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._payload(branchIds=[]), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert User.objects.filter(email='newuser@test.com').exists()

    def test_admin_can_create_user_with_branch(self, api_client, admin_user, branch):
        api_client.force_authenticate(user=admin_user)
        payload = self._payload(email='branchuser@test.com', branchIds=[str(branch.id)])
        response = api_client.post(reverse(self.URL), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        created = User.objects.get(email='branchuser@test.com')
        assert created.branches.filter(id=branch.id).exists()

    def test_single_branch_becomes_active_branch(self, api_client, admin_user, branch):
        """Assigning exactly one branch auto-sets it as the active branch."""
        api_client.force_authenticate(user=admin_user)
        payload = self._payload(email='onebranch@test.com', branchIds=[str(branch.id)])
        api_client.post(reverse(self.URL), payload, format='json')

        user = User.objects.get(email='onebranch@test.com')
        assert user.branch_id == branch.id

    def test_create_requires_branch_when_branch_exists(
        self, api_client, admin_user, branch
    ):
        """At least one branch is required when the clinic has any branches."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL), self._payload(), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_mismatched_passwords_returns_400(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(password2='WrongPass123!'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_with_missing_passwords_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        payload = self._payload()
        payload.pop('password2')
        response = api_client.post(reverse(self.URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_new_user_receives_default_role_permissions(self, api_client, admin_user, branch):
        """Default permission set for the chosen role is applied on creation."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(email='dentistnew@test.com', role='dentist', branchIds=[str(branch.id)]),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        created = User.objects.get(email='dentistnew@test.com')
        assert set(created.userPermissions) == set(User.DEFAULT_ROLE_PERMISSIONS['dentist'])

    def test_non_admin_cannot_create_user(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(email='forbidden@test.com'),
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_duplicate_email_returns_400(self, api_client, admin_user, dentist_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.URL),
            self._payload(email=dentist_user.email),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /auth/me/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUserProfileAPIView:
    URL = 'view_user'

    def test_authenticated_user_sees_own_profile(self, api_client, dentist_user):
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['email'] == dentist_user.email
        assert response.data['data']['name'] == dentist_user.name

    def test_response_contains_expected_fields(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for field in ('id', 'email', 'name', 'role', 'activeBranchId', 'branchIds', 'isActive'):
            assert field in response.data['data'], f"Missing field: {field}"

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_admin_profile_includes_permissions_field(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'permissions' in response.data['data']

    def test_non_admin_profile_excludes_permissions_field(
        self, api_client, dentist_user
    ):
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'permissions' not in response.data['data']

    def test_active_branch_id_reflected_in_profile(
        self, api_client, dentist_user, branch
    ):
        dentist_user.branch = branch
        dentist_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.URL))

        assert str(response.data['data']['activeBranchId']) == str(branch.id)

    def test_branch_ids_list_reflects_assigned_branches(
        self, api_client, dentist_user, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        dentist_user.branches.set([b1, b2])

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.URL))

        returned_ids = {str(bid) for bid in response.data['data']['branchIds']}
        assert str(b1.id) in returned_ids
        assert str(b2.id) in returned_ids


# ══════════════════════════════════════════════════════════════════════════════
# GET | PATCH | DELETE  /users/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeleteUserAPIView:

    def _url(self, user_id):
        return reverse('retrieve_update_delete_user', kwargs={'id': user_id})

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_any_user(self, api_client, admin_user, dentist_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(dentist_user.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['email'] == dentist_user.email

    def test_authenticated_user_can_retrieve_own_profile(
        self, api_client, receptionist_user
    ):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(self._url(receptionist_user.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['email'] == receptionist_user.email

    def test_nonexistent_user_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(self._url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    # ── UPDATE – role & permissions ───────────────────────────────────────────

    def test_admin_can_update_role_and_permissions(
        self, api_client, admin_user, receptionist_user
    ):
        api_client.force_authenticate(user=admin_user)
        payload = {
            'name': 'Updated Receptionist',
            'email': 'updated_receptionist@test.com',
            'role': 'Dentist',
            'permissions': {
                'view.patients': True,
                'view.patientDetail': True,
                'create.patient': True,
                'update.patient': True,
                'delete.patient': False,
                'view.visits': True,
                'create.visit': True,
            },
        }
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)

        receptionist_user.refresh_from_db()
        assert receptionist_user.name == 'Updated Receptionist'
        assert receptionist_user.email == 'updated_receptionist@test.com'
        assert receptionist_user.role == 'dentist'
        assert 'view.patientDetail' in receptionist_user.userPermissions
        assert 'create.visit' in receptionist_user.userPermissions
        assert 'delete.patient' not in receptionist_user.userPermissions

    def test_non_admin_cannot_change_own_role_or_permissions(
        self, api_client, receptionist_user
    ):
        """role/permissions fields are stripped from the serializer for non-admins."""
        api_client.force_authenticate(user=receptionist_user)
        original_role = receptionist_user.role
        original_perms = list(receptionist_user.userPermissions)

        payload = {
            'name': 'Updated Name',
            'role': 'Admin',
            'permissions': {'view.patients': True, 'view.patientDetail': True},
        }
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)

        receptionist_user.refresh_from_db()
        assert receptionist_user.name == 'Updated Name'       #ame update went through
        assert receptionist_user.role == original_role          # role unchanged
        assert receptionist_user.userPermissions == original_perms  # permissions unchanged

    def test_admin_can_add_permission_to_user(
        self, api_client, admin_user, receptionist_user
    ):
        """Granting a permission not previously held by the user adds it to the list."""
        target_perm = 'view.patientDetail'
        receptionist_user.userPermissions = [
            p for p in receptionist_user.userPermissions if p != target_perm
        ]
        receptionist_user.save(update_fields=['userPermissions'])

        api_client.force_authenticate(user=admin_user)
        payload = {'permissions': {target_perm: True}}
        api_client.patch(self._url(receptionist_user.id), payload, format='json')

        receptionist_user.refresh_from_db()
        assert target_perm in receptionist_user.userPermissions

    def test_admin_can_revoke_permission_from_user(
        self, api_client, admin_user, receptionist_user
    ):
        """Setting a permission to False removes it from the user's permission list."""
        target_perm = 'view.patients'
        if target_perm not in receptionist_user.userPermissions:
            receptionist_user.userPermissions.append(target_perm)
            receptionist_user.save(update_fields=['userPermissions'])

        api_client.force_authenticate(user=admin_user)
        payload = {'permissions': {target_perm: False}}
        api_client.patch(self._url(receptionist_user.id), payload, format='json')

        receptionist_user.refresh_from_db()
        assert target_perm not in receptionist_user.userPermissions

    # ── UPDATE – branches ─────────────────────────────────────────────────────

    def test_admin_can_assign_branches_to_user(
        self, api_client, admin_user, dentist_user, branch
    ):
        api_client.force_authenticate(user=admin_user)
        payload = {'branchIds': [str(branch.id)]}
        response = api_client.patch(
            self._url(dentist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        dentist_user.refresh_from_db()
        assert dentist_user.branches.filter(id=branch.id).exists()

    def test_non_admin_branch_assignment_payload_is_ignored(
        self, api_client, receptionist_user, branch
    ):
        """branchIds is stripped from the serializer for non-admins."""
        api_client.force_authenticate(user=receptionist_user)
        payload = {'branchIds': [str(branch.id)]}
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        receptionist_user.refresh_from_db()
        assert not receptionist_user.branches.filter(id=branch.id).exists()

    def test_admin_can_activate_deactivate_user(
        self, api_client, admin_user, receptionist_user
    ):
        api_client.force_authenticate(user=admin_user)
        payload = {'isActive': False}
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        receptionist_user.refresh_from_db()
        assert receptionist_user.isActive is False

    def test_non_admin_cannot_toggle_isActive(
        self, api_client, receptionist_user
    ):
        """isActive is stripped from the serializer for non-admins."""
        api_client.force_authenticate(user=receptionist_user)
        payload = {'isActive': False}
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        receptionist_user.refresh_from_db()
        assert receptionist_user.isActive is True   # unchanged

    # ── UPDATE – password ─────────────────────────────────────────────────────

    def test_password_update_is_hashed(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'currentPassword': 'Password123',
            'newPassword': 'Strongpass123!',
            'newPassword2': 'Strongpass123!',
        }
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        receptionist_user.refresh_from_db()
        assert check_password('Strongpass123!', receptionist_user.password)

    def test_wrong_current_password_returns_400(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'currentPassword': 'WrongPassword!',
            'newPassword': 'Strongpass123!',
            'newPassword2': 'Strongpass123!',
        }
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_password_mismatch_returns_400(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'currentPassword': 'Password123',
            'newPassword': 'Strongpass123!',
            'newPassword2': 'DifferentPass123!',
        }
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_new_password_same_as_current_returns_400(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'currentPassword': 'Password123',
            'newPassword': 'Password123',
            'newPassword2': 'Password123',
        }
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_new_password_without_current_returns_400(self, api_client, receptionist_user):
        """Supplying newPassword but omitting currentPassword must be rejected."""
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'newPassword': 'Strongpass123!',
            'newPassword2': 'Strongpass123!',
        }
        response = api_client.patch(
            self._url(receptionist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_user_cannot_change_another_users_password(
        self, api_client, receptionist_user, dentist_user
    ):
        """Password fields are silently dropped when the target user != requester."""
        api_client.force_authenticate(user=receptionist_user)
        payload = {
            'currentPassword': 'Password123',
            'newPassword': 'Hackpass123!',
            'newPassword2': 'Hackpass123!',
        }
        response = api_client.patch(
            self._url(dentist_user.id), payload, format='json'
        )
        # Request succeeds but target's password must be unchanged
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        dentist_user.refresh_from_db()
        assert not check_password('Hackpass123!', dentist_user.password)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_soft_deletes_user(self, api_client, admin_user, receptionist_user):
        uid = receptionist_user.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(uid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        #efault manager (filters is_deleted=False) must not find the record
        assert not User.objects.filter(id=uid).exists()
        # all_objects bypasses that filter; record must exist and be flagged
        deleted = User.all_objects.get(id=uid)
        assert deleted.is_deleted is True
        assert deleted.isActive is False

    def test_non_admin_cannot_delete_user(
        self, api_client, receptionist_user, assistant_user
    ):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.delete(self._url(assistant_user.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_delete_user(self, api_client, receptionist_user):
        response = api_client.delete(self._url(receptionist_user.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_soft_deleting_dentist_nullifies_patient_and_appointment_doctor_refs(
        self,
        api_client,
        admin_user,
        dentist_user,
        patient_factory,
        procedure_factory,
        appointment_factory,
    ):
        """
        When a dentist is soft-deleted the manager should clear the doctor FK
        on their patients and nullify any pending/confirmed appointments.
        """
        from patients.models import Patient, Appointment

        patient = patient_factory(doctor=dentist_user)
        proc = procedure_factory()
        appt = appointment_factory(
            patient=patient, doctor=dentist_user, procedure=proc, status='pending'
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(self._url(dentist_user.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)

        patient.refresh_from_db()
        assert patient.doctor is None

        appt.refresh_from_db()
        assert appt.doctor is None


# ══════════════════════════════════════════════════════════════════════════════
# GET  /users/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUsersOptionsAPIView:
    URL = 'users_options'

    def test_authenticated_user_gets_options_payload(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'roleChoices' in response.data
        assert 'branchChoices' in response.data

    def test_role_choices_cover_all_defined_roles(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned_values = {c['value'] for c in response.data['roleChoices']}
        expected_values = {r.value for r in User.UserRoles}
        assert returned_values == expected_values

    def test_role_choices_include_display_labels(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        for choice in response.data['roleChoices']:
            assert 'label' in choice, "Each role choice must carry a human-readable label"

    def test_branch_choices_reflect_existing_branches(
        self, api_client, admin_user, branch_factory
    ):
        b1 = branch_factory(name='Alpha Branch')
        b2 = branch_factory(name='Beta Branch')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned_ids = {str(c['branchId']) for c in response.data['branchChoices']}
        assert str(b1.id) in returned_ids
        assert str(b2.id) in returned_ids

    def test_branch_choices_empty_when_no_branches_exist(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['branchChoices'] == []

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# POST  /activate-branch/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSetActiveBranchAPIView:
    URL = 'set_active_branch'

    def test_user_can_activate_branch_they_belong_to(
        self, api_client, dentist_user, branch
    ):
        dentist_user.branches.add(branch)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data == {'success': True}
        dentist_user.refresh_from_db()
        assert dentist_user.branch_id == branch.id

    def test_user_can_switch_between_branches(
        self, api_client, dentist_user, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        dentist_user.branches.set([b1, b2])
        dentist_user.branch = b1
        dentist_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            reverse(self.URL), {'branchId': str(b2.id)}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        dentist_user.refresh_from_db()
        assert dentist_user.branch_id == b2.id

    def test_user_cannot_activate_branch_they_dont_belong_to(
        self, api_client, dentist_user, branch
    ):
        #entist_user.branches does NOT include `branch`
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_missing_branch_id_returns_400_when_branch_exists(
        self, api_client, dentist_user, branch  #branch` fixture ensures a row exists
    ):
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(reverse(self.URL), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_nonexistent_branch_id_returns_404(self, api_client, dentist_user):
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            reverse(self.URL), {'branchId': str(uuid.uuid4())}, format='json'
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_unauthenticated_returns_401(self, api_client, branch):
        response = api_client.post(
            reverse(self.URL), {'branchId': str(branch.id)}, format='json'
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)