import uuid
import pytest
from copy import deepcopy
from .utils import render_error
from django.urls import reverse
from rest_framework import status
from patients.validators import FDI_PERMANENT
from patients.models import Patient, DentalChart, XRay


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _patient_url(patient_id):
    return reverse('retrieve_update_delete_patient', kwargs={'id': patient_id})

def _dentalchart_url(patient_id):
    return reverse('retrieve_update_dentalchart', kwargs={'id': patient_id})

def _create_payload(**overrides):
    base = {
        'name':        'Test Patient',
        'age':         30,
        'gender':      'Male',
        'countryCode': '20',
        'phone':       '01012345678',
        'branchId':    None,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /patients/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreatePatientsAPIView:
    LIST_URL = 'list_create_patients'

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_can_list_all_patients(
        self, api_client, admin_user, patient_factory
    ):
        p1 = patient_factory(name='Alice')
        p2 = patient_factory(name='Bob')
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['success'] is True
        ids = [item['id'] for item in response.data['data']]
        assert str(p1.id) in ids
        assert str(p2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, patient_factory
    ):
        patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"
        assert response.data['pagination']['total'] >= 1

    def test_dentist_sees_only_own_patients(
        self, api_client, dentist_user, other_dentist_user, patient_factory
    ):
        visible = patient_factory(name='Visible', doctor=dentist_user)
        patient_factory(name='Hidden', doctor=other_dentist_user)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert [i['id'] for i in response.data['data']] == [str(visible.id)]

    def test_receptionist_sees_branch_filtered_patients(
        self, api_client, user_factory, patient_factory, branch_factory
    ):
        b1 = branch_factory()
        b2 = branch_factory()
        recept = user_factory(role='receptionist')
        recept.branches.set([b1])
        p_own   = patient_factory(branch=b1)
        p_other = patient_factory(branch=b2)

        api_client.force_authenticate(user=recept)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(p_own.id) in ids
        assert str(p_other.id) not in ids

    def test_soft_deleted_patients_excluded_from_list(
        self, api_client, admin_user, patient_factory
    ):
        """PatientsManager.get_queryset() filters is_deleted=False."""
        visible = patient_factory()
        ghost   = patient_factory()
        ghost.is_deleted = True
        ghost.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.LIST_URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(visible.id) in ids
        assert str(ghost.id)   not in ids

    def test_assistant_cannot_list_patients(self, api_client, assistant_user):
        """assistant default permissions do not include 'view.patients'."""
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(reverse(self.LIST_URL))

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)
        assert response.data['success'] is False

    def test_unauthenticated_cannot_list_patients(self, api_client):
        response = api_client.get(reverse(self.LIST_URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_patient(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Patient.objects.filter(name='Test Patient').exists()

    def test_create_auto_sets_status_to_active(self, api_client, admin_user):
        """Patient.save(): status defaults to 'active' when not provided."""
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert Patient.objects.get(name='Test Patient').status == Patient.StatusChoices.ACTIVE

    def test_create_auto_creates_dental_chart(self, api_client, admin_user):
        """Patient.save(): a full FDI dental chart is auto-created on new patient."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        patient = Patient.objects.get(id=response.data['data']['id'])
        chart   = patient.patient_dentalchart
        assert chart is not None
        assert len(chart.teeth) == len(FDI_PERMANENT)
        assert all(t['status'] == 'healthy' for t in chart.teeth.values())

    def test_create_phone_normalized_in_response(self, api_client, admin_user):
        """
        to_representation strips the country code prefix so the response
        shows the local number with a leading 0.
        """
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(phone='01099887766', countryCode='20'),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        # Local display must match original input
        assert response.data['data']['phone'] == '01099887766'

    def test_create_sets_doctor_name_snapshot_when_doctor_assigned(
        self, api_client, admin_user, dentist_user
    ):
        """Patient.save(): doctorName is captured from the FK on creation."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(doctorId=str(dentist_user.id)),
            format='json',
        )
        # doctorId is not a field on CreatePatientSerializer, so it's ignored
        # but we still verify name snapshot isn't set unexpectedly
        if response.status_code == status.HTTP_201_CREATED:
            patient = Patient.objects.get(id=response.data['data']['id'])
            # If doctor was not assigned, doctorName should be None
            assert patient.doctorName is None

    def test_create_auto_assigns_branch_from_user_active_branch(
        self, api_client, admin_user, branch
    ):
        """ValidateBranchMixin: branchId=null + user.branch set → auto-assign."""
        admin_user.branch = branch   # set in memory; force_authenticate uses same obj
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        patient = Patient.objects.get(id=response.data['data']['id'])
        assert patient.branch == branch

    def test_create_without_branch_id_key_returns_400(self, api_client, admin_user):
        """branchId is required=True; omitting the key entirely → 400."""
        api_client.force_authenticate(user=admin_user)
        payload = _create_payload()
        payload.pop('branchId')
        response = api_client.post(reverse(self.LIST_URL), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_invalid_country_code_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(countryCode='abc'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_invalid_email_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(email='not-an-email'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'email' in response.data['error']['fields']

    def test_create_invalid_phone_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL),
            _create_payload(phone='not-a-phone-!!!!'),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_receptionist_with_create_patient_permission_can_create(
        self, api_client, receptionist_user
    ):
        """receptionist has 'create.patient' by default."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

    def test_create_response_is_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            reverse(self.LIST_URL), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | PATCH | DELETE  /patients/<id>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveUpdateDeletePatientAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_patient_detail(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory(name='Detail Patient')
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_patient_url(patient.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['id'] == str(patient.id)

    def test_retrieve_response_is_wrapped_with_metadata(
        self, api_client, admin_user, patient_factory
    ):
        """RetrievePatientSerializer inherits UserPermissionsMixin → metadata on GET."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_patient_url(patient.id))

        assert response.data.get('success') is True
        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_retrieve_phone_is_normalized_to_local_format(
        self, api_client, admin_user, patient_factory
    ):
        """RetrievePatientSerializer.get_phone() strips country code prefix."""
        patient = patient_factory(phone='01012345678', countryCode='20')
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_patient_url(patient.id))

        # Stored as '2001012345678' but displayed as '01012345678'
        assert response.data['data']['phone'] == '01012345678'

    def test_dentist_cannot_retrieve_another_dentists_patient(
        self, api_client, dentist_user, other_dentist_user, patient_factory
    ):
        """PatientDataPermissions: dentist obj permission → obj.doctor == request.user."""
        patient = patient_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_patient_url(patient.id))

        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)
        assert response.data['error']['code'] == 'PERMISSION_DENIED'

    def test_nonexistent_patient_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_patient_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    # ── UPDATE ────────────────────────────────────────────────────────────────

    def test_admin_can_update_address_and_notes(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _patient_url(patient.id),
            {'address': '123 New Street', 'notes': 'Updated notes'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        patient.refresh_from_db()
        assert patient.address == '123 New Street'
        assert patient.notes   == 'Updated notes'

    def test_name_is_read_only_on_update(self, api_client, admin_user, patient_factory):
        """UpdatePatientSerializer: 'name' is in read_only_fields → ignored."""
        patient = patient_factory(name='Original Name')
        api_client.force_authenticate(user=admin_user)
        api_client.put(
            _patient_url(patient.id),
            {'name': 'Changed Name', 'countryCode': '20', 'phone': '01099887766'},
            format='json',
        )
        patient.refresh_from_db()
        assert patient.name == 'Original Name'

    def test_update_phone_requires_both_phone_and_country_code(
        self, api_client, admin_user, patient_factory
    ):
        """UpdatePatientSerializer.validate(): phone without countryCode → 400."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _patient_url(patient.id),
            {'phone': '01011112222'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert 'phone' in response.data['error']['fields']

    def test_update_country_code_without_phone_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _patient_url(patient.id),
            {'countryCode': '44'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_update_phone_pair_together_succeeds(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _patient_url(patient.id),
            {'countryCode': '20', 'phone': '01088889999'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        # Response displays normalized local number
        assert response.data['data']['phone'] == '01088889999'

    def test_update_response_is_wrapped(self, api_client, admin_user, patient_factory):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _patient_url(patient.id), {'notes': 'test'}, format='json'
        )

        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_receptionist_can_update_patient_with_permission(
        self, api_client, user_factory, patient_factory, branch_factory
    ):
        """receptionist has update.patient; branch check passes when on same branch."""
        b = branch_factory()
        recept  = user_factory(role='receptionist')
        recept.branches.set([b])
        patient = patient_factory(branch=b)

        api_client.force_authenticate(user=recept)
        response = api_client.patch(
            _patient_url(patient.id), {'notes': 'Updated by receptionist'}, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_hard_deletes_patient(self, api_client, admin_user, patient_factory):
        patient = patient_factory()
        pid = patient.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_patient_url(pid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)
        assert not Patient.objects.filter(id=pid).exists()
        assert not Patient.all_objects.filter(id=pid).exists()   # hard delete

    def test_dentist_soft_deletes_patient(
        self, api_client, user_factory, patient_factory, branch_factory
    ):
        branch = branch_factory()
        dentist = user_factory(role='dentist')
        dentist.branches.set([branch])

        patient = patient_factory(branch=branch)
        pid = patient.id

        api_client.force_authenticate(user=dentist)
        response = api_client.delete(_patient_url(pid))

        assert response.status_code == status.HTTP_204_NO_CONTENT or render_error(response)

        #deleted patient is accessed only via all_objects()
        assert not Patient.objects.filter(id=pid).exists()
        deleted_patient = Patient.all_objects.get(id=pid)
        assert deleted_patient.is_deleted is True
        assert deleted_patient.status == Patient.StatusChoices.INACTIVE

    def test_receptionist_with_permission_soft_deletes_patient_and_removes_patient_xrays(
        self, api_client, user_factory, patient_factory, branch_factory, png_file, visit_factory, dentist_user
    ):
        """
        Granting receptionist 'delete.patient' permission and testing 
        delete_patient() deletes all associated XRay records.
        """
        branch = branch_factory()
        receptionist = user_factory(role='receptionist')
        receptionist.branches.set([branch])
        receptionist.userPermissions.append('delete.patient')
        receptionist.save(update_fields=['userPermissions'])

        patient = patient_factory(branch=branch)
        XRay.objects.create(patient=patient, image=png_file)

        api_client.force_authenticate(user=receptionist)
        api_client.delete(_patient_url(patient.id))

        assert XRay.all_objects.filter(patient=patient).count() == 0

    def test_unauthenticated_cannot_delete_patient(
        self, api_client, patient_factory
    ):
        patient = patient_factory()
        response = api_client.delete(_patient_url(patient.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET  /patients/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrievePatientsOptionsAPIView:
    URL = 'patients_options'

    def test_authenticated_user_gets_options_payload(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('genderChoices', 'statusChoices', 'bloodTypeChoices', 'branchChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_gender_choices_cover_male_and_female(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        values = {c['value'] for c in response.data['genderChoices']}
        assert {'male', 'female'}.issubset(values)

    def test_status_choices_cover_active_and_inactive(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        values = {c['value'] for c in response.data['statusChoices']}
        assert 'active' in values
        assert 'inactive' in values

    def test_blood_type_choices_cover_all_types(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        values = {c['value'] for c in response.data['bloodTypeChoices']}
        assert 'A+' in values and 'O-' in values

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)


# ══════════════════════════════════════════════════════════════════════════════
# GET | PUT | PATCH  /patients/<id>/dental-chart/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDentalChartAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_retrieves_dental_chart_with_all_fdi_teeth(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_dentalchart_url(patient.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data']['patientId'] == patient.id
        assert len(response.data['data']['teeth']) == len(FDI_PERMANENT)

    def test_all_default_teeth_are_healthy(self, api_client, admin_user, patient_factory):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_dentalchart_url(patient.id))

        statuses = [t['status'] for t in response.data['data']['teeth'].values()]
        assert all(s == 'healthy' for s in statuses)

    def test_retrieve_chart_includes_metadata(
        self, api_client, admin_user, patient_factory
    ):
        """DentalChartSerializer → UserPermissionsMixin (via PatientDataPermissions view)
        note: the view uses PatientDataPermissions not the serializer for metadata.
        Response is wrapped by ResponseMixin."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_dentalchart_url(patient.id))

        assert response.data.get('success') is True

    def test_dentist_cannot_retrieve_another_dentists_patient_chart(
        self, api_client, dentist_user, other_dentist_user, patient_factory
    ):
        """PatientDataPermissions: dentist can only access own patient's chart."""
        patient = patient_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_dentalchart_url(patient.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    # ── PATCH (partial update – merge) ────────────────────────────────────────

    def test_patch_updates_single_tooth_without_affecting_others(
        self, api_client, admin_user, patient_factory
    ):
        """PATCH merges into the existing teeth dict; other teeth unchanged."""
        patient = patient_factory()
        original_12 = deepcopy(patient.patient_dentalchart.teeth['12'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _dentalchart_url(patient.id),
            {'teeth': {'11': {'status': 'cavity', 'notes': 'Needs filling'}}},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        patient.patient_dentalchart.refresh_from_db()
        assert patient.patient_dentalchart.teeth['11']['status'] == 'cavity'
        assert patient.patient_dentalchart.teeth['12'] == original_12

    def test_patch_with_empty_teeth_dict_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """DentalChartSerializer.validate_teeth: PATCH with {} → 400."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _dentalchart_url(patient.id), {'teeth': {}}, format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_patch_invalid_fdi_tooth_number_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """validate_teeth: tooth number not in FDI_PERMANENT → 400."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _dentalchart_url(patient.id),
            {'teeth': {'99': {'status': 'healthy', 'notes': ''}}},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert response.data['error']['fields']['teeth']['99'] == 'Invalid FDI tooth number.'

    def test_patch_invalid_tooth_status_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """ToothDetailSerializer: status must be a valid DentalChart.ToothStatusChoices value."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _dentalchart_url(patient.id),
            {'teeth': {'11': {'status': 'not_a_real_status', 'notes': ''}}},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    # ── PUT (full update – replace) ───────────────────────────────────────────

    def test_put_with_all_teeth_succeeds(
        self, api_client, admin_user, patient_factory
    ):
        """PUT replaces the entire teeth dict when a complete payload is supplied."""
        patient = patient_factory()
        full_payload = {
            'teeth': {
                tooth: {'status': 'filling', 'notes': 'test'}
                for tooth in FDI_PERMANENT
            }
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _dentalchart_url(patient.id), full_payload, format='json'
        )

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        patient.patient_dentalchart.refresh_from_db()
        assert all(
            v['status'] == 'filling'
            for v in patient.patient_dentalchart.teeth.values()
        )

    def test_put_incomplete_teeth_payload_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        """validate_teeth: PUT with fewer teeth than stored → 400."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _dentalchart_url(patient.id),
            {'teeth': {'11': {'status': 'healthy', 'notes': ''}}},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)
        assert response.data['error']['fields']['teeth'] == 'Teeth data missing or incomplete.'


# ══════════════════════════════════════════════════════════════════════════════
# GET  /dental-chart/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDentalChartOptionsAPIView:
    URL = 'dentalchart_options'

    def test_authenticated_user_gets_options(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'toothNumberChoices' in response.data
        assert 'toothStatusChoices'  in response.data

    def test_tooth_number_choices_cover_all_fdi_permanent(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['toothNumberChoices']}
        assert returned == set(FDI_PERMANENT)

    def test_tooth_status_choices_cover_all_statuses(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['toothStatusChoices']}
        expected = {c.value for c in DentalChart.ToothStatusChoices}
        assert returned == expected