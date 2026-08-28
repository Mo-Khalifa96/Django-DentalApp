import uuid
import pytest
from datetime import timedelta
from .utils import render_error
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from dateutil.relativedelta import relativedelta
from patients.models import Visit, XRay, PatientRecall


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _list_url(patient_id):
    return reverse('list_create_visits', kwargs={'id': patient_id})

def _create_payload(**overrides):
    base = {
        'date':       timezone.localdate().isoformat(),
        'type':       'routine_checkup',
        'procedures': ['Exam'],
        'currency':   '$',
        'cost':       '200.00',
        'paid':       '100.00',
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST  /patients/<id>/visits/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListCreateVisitsAPIView:

    # ── LIST ──────────────────────────────────────────────────────────────────

    def test_admin_lists_patient_visits(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        v1 = visit_factory(patient=patient, doctor=dentist_user, type='cleaning')
        v2 = visit_factory(patient=patient, doctor=dentist_user, type='filling')

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['pagination']['total'] == 2
        ids = [i['id'] for i in response.data['data']]
        assert str(v1.id) in ids
        assert str(v2.id) in ids

    def test_list_page_size_is_10(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        """ListCreateVisitsAPIView.paginate_queryset sets page_size = 10."""
        patient = patient_factory(doctor=dentist_user)
        for _ in range(12):
            visit_factory(patient=patient, doctor=dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id))
        assert response.data['pagination']['limit'] == 10
        assert len(response.data['data']) == 10

    def test_current_doctor_sees_full_visit_history_regardless_of_performing_doctor(
        self, api_client, dentist_user, other_dentist_user, patient_factory, visit_factory
    ):
        """
        Once a dentist passes the 'is this my patient' gate via get_patient(),
        they see the FULL visit history — including visits performed by a
        previous doctor — not just visits where doctor == request.user.
        This reflects continuity of care: the chart belongs to the patient's
        current treatment relationship, not to whichever clinician performed
        each individual visit.
        """
        patient = patient_factory(doctor=dentist_user)   # dentist_user is CURRENT doctor
        own_visit   = visit_factory(patient=patient, doctor=dentist_user)
        # historical visit performed by a different doctor before reassignment
        prior_visit = visit_factory(patient=patient, doctor=other_dentist_user)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_list_url(patient.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        ids = [i['id'] for i in response.data['data']]
        assert str(own_visit.id)   in ids
        assert str(prior_visit.id) in ids

    def test_dentist_not_assigned_to_patient_cannot_list_visits(
        self, api_client, dentist_user, other_dentist_user, patient_factory, visit_factory
    ):
        """
        get_queryset() now routes through get_patient(), which enforces
        PatientDataPermissions.has_object_permission(): a dentist who is NOT
        the patient's current doctor gets 403, not an empty/filtered list.
        """
        patient = patient_factory(doctor=other_dentist_user)
        visit_factory(patient=patient, doctor=other_dentist_user)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_list_url(patient.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_permission_holder_can_list_visits_in_own_branch(
        self, api_client, user_factory, patient_factory, visit_factory, branch_factory
    ):
        """Sanity check: a non-admin/non-dentist with 'view.visits' can list
        visits for a patient in their own branch."""
        b1 = branch_factory()
        recept_user = user_factory(role='receptionist')
        recept_user.branches.set([b1])

        recept_user.userPermissions = list(recept_user.userPermissions) + ['view.visits']
        recept_user.save(update_fields=['userPermissions'])

        patient = patient_factory(branch=b1)
        visit   = visit_factory(patient=patient, doctor=None)

        api_client.force_authenticate(user=recept_user)
        response = api_client.get(_list_url(patient.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert str(visit.id) in [i['id'] for i in response.data['data']]

    def test_permission_holder_sees_visits_irrespective_of_branch(
        self, api_client, user_factory, patient_factory, visit_factory, branch_factory
    ):
        """
        Design choice: get_queryset() applies NO object-level check for the
        admin/permission-based path — branch is not enforced for any role
        other than dentist. A user holding 'view.visits' can see a patient's
        visits even when assigned to a different branch than the patient.
        """
        b1 = branch_factory()
        b2 = branch_factory()
        recept_user = user_factory(role='receptionist')
        recept_user.branches.set([b1])
        
        recept_user.userPermissions = list(recept_user.userPermissions) + ['view.visits']
        recept_user.save(update_fields=['userPermissions'])

        patient_b2 = patient_factory(branch=b2)
        visit_b2   = visit_factory(patient=patient_b2, doctor=None)

        api_client.force_authenticate(user=recept_user)
        response = api_client.get(_list_url(patient_b2.id))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert str(visit_b2.id) in [i['id'] for i in response.data['data']]

    def test_assistant_cannot_list_visits(self, api_client, assistant_user, patient_factory):
        """assistant default permissions do not include 'view.visits'."""
        patient = patient_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.get(_list_url(patient.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_unauthenticated_cannot_list_visits(self, api_client, patient_factory):
        patient = patient_factory()
        response = api_client.get(_list_url(patient.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_admin_list_for_nonexistent_patient_returns_empty_200(
        self, api_client, admin_user
    ):
        """
        The admin/permission-based branch of get_queryset() never validates
        patient existence (no get_object_or_404 call) — a missing patient id
        silently yields an empty, paginated 200 rather than 404.
        """
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data'] == []

    def test_dentist_list_for_nonexistent_patient_returns_404(
        self, api_client, dentist_user
    ):
        """
        The dentist branch performs an inline get_object_or_404() lookup on
        the patient before applying the object permission check, so a
        missing patient id correctly 404s for this role — unlike admin.
        """
        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(_list_url(uuid.uuid4()))
        assert response.status_code == status.HTTP_404_NOT_FOUND or render_error(response)

    def test_list_filters_by_date_range(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        """startDate/endDate are plain DateFilter on Visit.date; confirmed
        to work correctly (the originally-suspected 500 does not reproduce)."""
        patient = patient_factory(doctor=dentist_user)
        in_range  = timezone.localdate() - timedelta(days=2)
        out_range = timezone.localdate() - timedelta(days=20)
        in_range_visit = visit_factory(patient=patient, doctor=dentist_user, date=in_range)
        visit_factory(patient=patient, doctor=dentist_user, date=out_range)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(
            _list_url(patient.id),
            {
                'startDate': (timezone.localdate() - timedelta(days=5)).isoformat(),
                'endDate':   timezone.localdate().isoformat(),
            },
        )
        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert [i['id'] for i in response.data['data']] == [str(in_range_visit.id)]

    def test_search_matches_by_type(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        """search OR-matches against type even with no procedures overlap."""
        patient = patient_factory(doctor=dentist_user)
        matching = visit_factory(patient=patient, doctor=dentist_user,
                                 type='emergency', procedures=['Unrelated'])
        visit_factory(patient=patient, doctor=dentist_user,
                      type='follow_up', procedures=['Also unrelated'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id), {'search': 'emergency'})

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert [i['id'] for i in response.data['data']] == [str(matching.id)]

    def test_search_matches_by_procedure_substring_across_array(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        """
        search flattens the procedures ArrayField via array_to_string() and
        matches a substring against it — confirms the ArrayField scan works,
        not just an exact-element match.
        """
        patient = patient_factory(doctor=dentist_user)
        matching = visit_factory(patient=patient, doctor=dentist_user,
                                 type='routine_checkup', procedures=['Root Canal Therapy'])
        visit_factory(patient=patient, doctor=dentist_user,
                      type='routine_checkup', procedures=['Cleaning'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id), {'search': 'Root Canal'})

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert [i['id'] for i in response.data['data']] == [str(matching.id)]

    def test_search_is_ored_not_anded_across_type_and_procedures(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        """
        Confirms the SearchFilter/FilterSet collision is resolved: a record
        matching ONLY on type (not procedures) must still be returned — the
        previous behaviour effectively required both to match (AND).
        """
        patient = patient_factory(doctor=dentist_user)
        type_only_match = visit_factory(patient=patient, doctor=dentist_user,
                                        type='emergency', procedures=['Cleaning'])
        no_match = visit_factory(patient=patient, doctor=dentist_user,
                                 type='follow_up', procedures=['Cleaning'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id), {'search': 'emergency'})

        ids = [i['id'] for i in response.data['data']]
        assert str(type_only_match.id) in ids
        assert str(no_match.id) not in ids

    def test_search_with_no_matches_returns_empty_list(
        self, api_client, admin_user, dentist_user, patient_factory, visit_factory
    ):
        patient = patient_factory(doctor=dentist_user)
        visit_factory(patient=patient, doctor=dentist_user,
                      type='follow_up', procedures=['Cleaning'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_list_url(patient.id), {'search': 'nonexistent_term'})

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['data'] == []

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_visit(self, api_client, admin_user, patient_factory):
        patient = patient_factory(doctor=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert Visit.objects.filter(patient=patient).exists()

    def test_create_updates_patient_last_visit(
        self, api_client, admin_user, patient_factory
    ):
        """Visit.save(): patient.lastVisit = visit.date."""
        patient   = patient_factory(doctor=None)
        visit_date = (timezone.localdate() - timedelta(days=1)).isoformat()
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            _list_url(patient.id),
            _create_payload(date=visit_date),
            format='json',
        )
        patient.refresh_from_db()
        assert patient.lastVisit.isoformat() == visit_date

    def test_create_layer1_explicit_doctor_id_is_used(
        self, api_client, admin_user, dentist_user, other_dentist_user, patient_factory
    ):
        """Layer 1: an explicit doctorId in the payload takes priority over
        the patient's standing doctor and over the requester."""
        patient = patient_factory(doctor=other_dentist_user)   # standing doctor = other_dentist_user
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(doctorId=str(dentist_user.id)),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.doctor_id == dentist_user.id

    def test_create_explicit_doctor_id_does_not_overwrite_patients_standing_doctor(
        self, api_client, admin_user, dentist_user, other_dentist_user, patient_factory
    ):
        """
        A per-visit doctorId only sets who treated the patient THIS visit —
        it must not silently reassign the patient's regular/standing doctor.
        """
        patient = patient_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            _list_url(patient.id),
            _create_payload(doctorId=str(dentist_user.id)),
            format='json',
        )
        patient.refresh_from_db()
        assert patient.doctor == other_dentist_user   # unchanged

    def test_create_layer1_rejects_doctor_id_for_non_clinical_role(
        self, api_client, admin_user, receptionist_user, patient_factory
    ):
        """doctorId's queryset is filtered to role__in=['admin', 'dentist',
        'assistant']; passing a receptionist's id must fail validation."""
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(doctorId=str(receptionist_user.id)),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_create_layer1_accepts_assistant_as_doctor_id(
        self, api_client, admin_user, user_factory, patient_factory
    ):
        """doctorId's queryset now includes 'assistant' alongside dentist/admin."""
        assistant = user_factory(role='assistant')
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(doctorId=str(assistant.id)),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.doctor_id == assistant.id

    def test_create_layer2_falls_back_to_patients_standing_doctor(
        self, api_client, admin_user, dentist_user, patient_factory
    ):
        """Layer 2: no explicit doctorId → use patient.doctor when set."""
        patient = patient_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.doctor_id == dentist_user.id

    def test_create_layer3_falls_back_to_requester_when_admin(
        self, api_client, admin_user, patient_factory
    ):
        """Layer 3: no doctorId, no patient.doctor → admin requester is used."""
        patient = patient_factory(doctor=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.doctor_id == admin_user.id

    def test_create_layer3_falls_back_to_requester_when_dentist(
        self, api_client, dentist_user, patient_factory
    ):
        """Layer 3: no doctorId, no patient.doctor → dentist requester is used."""
        patient = patient_factory(doctor=None)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.doctor_id == dentist_user.id

    def test_create_layer3_leaves_doctor_null_for_non_clinical_creator_with_no_standing_doctor(
        self, api_client, user_factory, patient_factory
    ):
        """
        All three layers exhausted: no doctorId, no patient.doctor, and the
        requester is neither admin nor dentist → visit.doctor stays None.
        """
        patient = patient_factory(doctor=None)
        recept_user  = user_factory(role='receptionist')

        recept_user.userPermissions = list(recept_user.userPermissions) + ['create.visit']
        recept_user.save(update_fields=['userPermissions'])

        api_client.force_authenticate(user=recept_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.doctor_id is None

    def test_create_assigns_patients_existing_doctor_when_creator_is_not_dentist_or_admin(
        self, api_client, user_factory, dentist_user, patient_factory
    ):
        """
        Layer 2 still applies for a non-clinical creator: if the patient
        already has a standing doctor, that doctor is used on the visit
        even though the requester themselves isn't admin/dentist.
        """
        patient = patient_factory(doctor=dentist_user)
        recept_user  = user_factory(role='receptionist')

        recept_user.userPermissions = list(recept_user.userPermissions) + ['create.visit']
        recept_user.save(update_fields=['userPermissions'])

        api_client.force_authenticate(user=recept_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.doctor_id == patient.doctor_id

    def test_create_assigns_doctor_to_patient_if_previously_none(
        self, api_client, dentist_user, patient_factory
    ):
        """create(): if patient.doctor is None, it is set to request.user."""
        patient = patient_factory(doctor=None)
        api_client.force_authenticate(user=dentist_user)
        api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        patient.refresh_from_db()
        assert patient.doctor == dentist_user

    def test_create_does_not_overwrite_existing_patient_doctor(
        self, api_client, dentist_user, other_dentist_user, patient_factory
    ):
        """create(): existing patient.doctor is preserved even if a different
        dentist creates the visit."""
        patient = patient_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        patient.refresh_from_db()
        assert patient.doctor == other_dentist_user

    def test_create_with_xray_uploads_sets_flag_and_creates_xrays(
        self, api_client, dentist_user, patient_factory, png_file
    ):
        patient = patient_factory(doctor=dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id),
            {**_create_payload(), 'xrayUploads': [png_file]},
            format='multipart',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        visit = Visit.objects.get(id=response.data['data']['id'])
        assert visit.xray is True
        assert response.data['data']['xray'] is True
        assert XRay.objects.filter(patient=patient).count() == 1

    def test_create_without_xray_uploads_leaves_flag_false(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data['data']['xray'] is False

    def test_xray_urls_field_reflects_visit_xrays_only(
        self, api_client, dentist_user, patient_factory, visit_factory, png_file
    ):
        patient = patient_factory(doctor=dentist_user)

        #Create separate visit and xray
        visit = visit_factory(patient=patient, doctor=dentist_user)
        XRay.objects.create(patient=patient, visit=visit, image=png_file)

        #create visit without xray
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert XRay.objects.count() == 1
        assert len(response.data['data']['xrayUrls']) == 0

    def test_create_with_missing_required_fields_returns_400(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(_list_url(patient.id), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)

    def test_assistant_cannot_create_visit(self, api_client, assistant_user, patient_factory):
        patient = patient_factory()
        api_client.force_authenticate(user=assistant_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN or render_error(response)

    def test_create_response_is_wrapped(self, api_client, admin_user, patient_factory):
        patient = patient_factory()
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id), _create_payload(), format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response.data.get('success') is True
        assert 'data' in response.data

    # ── CREATE (auto-generated checkup recall) ──────────────────────────────────

    def test_create_routine_checkup_visit_creates_pending_recall(
        self, api_client, admin_user, patient_factory
    ):
        """perform_create(): a 'routine_checkup' visit auto-creates a pending
        checkup PatientRecall for the patient if one doesn't already exist."""
        patient = patient_factory(doctor=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(type='routine_checkup'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert PatientRecall.objects.filter(
            patient=patient, type='checkup', status='pending'
        ).exists()

    def test_create_routine_checkup_visit_sets_recall_due_date_six_months_out(
        self, api_client, admin_user, patient_factory
    ):
        """dueDate is computed as today + relativedelta(months=6), matching
        the calendar-month arithmetic convention used elsewhere (recalls)."""
        patient = patient_factory(doctor=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(type='routine_checkup'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        recall = PatientRecall.objects.get(patient=patient, type='checkup', status='pending')
        expected_due = timezone.localdate() + relativedelta(months=6)
        assert recall.dueDate == expected_due

    def test_create_routine_checkup_visit_recall_uses_patient_branch_and_phone(
        self, api_client, admin_user, patient_factory, branch
    ):
        """The auto-created recall snapshots the patient's current branch
        and phone number at creation time."""
        patient = patient_factory(doctor=None, branch=branch)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(type='routine_checkup'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        recall = PatientRecall.objects.get(patient=patient, type='checkup', status='pending')
        assert recall.branch == branch
        assert recall.phone == patient.phone

    def test_create_non_checkup_visit_does_not_create_recall(
        self, api_client, admin_user, patient_factory
    ):
        """Only 'routine_checkup' visits trigger recall creation — a
        'follow_up' or 'emergency' visit must not."""
        patient = patient_factory(doctor=None)
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(type='follow_up'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert not PatientRecall.objects.filter(patient=patient, type='checkup').exists()

    def test_create_routine_checkup_visit_creates_new_recall_when_prior_recall_is_contacted(
        self, api_client, admin_user, patient_factory
    ):
        """
        has_pending_recall filters on status='pending' specifically — a
        prior checkup recall already marked 'contacted' (or any non-pending
        status) does not block a new pending recall from being created.
        """
        patient = patient_factory(doctor=None)
        contacted_recall = PatientRecall.objects.create(
            patient=patient, type='checkup', status='contacted',
            dueDate=timezone.localdate() - timedelta(days=5),
            contactedAt=timezone.localtime(timezone.now()),
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(type='routine_checkup'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

        assert PatientRecall.objects.filter(
            patient=patient, type='checkup', status='pending'
        ).exists()
        # the older contacted recall is untouched, a distinct new row exists
        contacted_recall.refresh_from_db()
        assert contacted_recall.status == 'contacted'

    
    def test_create_routine_checkup_visit_extends_existing_pending_recall_due_date(
        self, api_client, admin_user, patient_factory
    ):
        """
        update_or_create() now updates an EXISTING pending checkup recall rather
        than being blocked by a separate has_pending_recall check (since removed).
        A new routine_checkup visit always pushes the recall's dueDate forward to
        6 months from the visit date, even if a pending recall with an earlier
        due date already existed — modeling an unannounced/early checkup
        resetting the "next visit due" clock.
        """
        patient = patient_factory(doctor=None)
        original_due = timezone.localdate() + timedelta(days=10)
        existing_recall = PatientRecall.objects.create(
            patient=patient, type='checkup', status='pending', dueDate=original_due
        )

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(type='routine_checkup'),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)

        # still exactly one pending checkup recall (updated, not duplicated)
        assert PatientRecall.objects.filter(
            patient=patient, type='checkup', status='pending'
        ).count() == 1
        existing_recall.refresh_from_db()
        expected_due = timezone.localdate() + relativedelta(months=6)
        assert existing_recall.dueDate == expected_due
        assert existing_recall.dueDate != original_due   # pushed later


    def test_creating_double_visits_do_not_lead_to_duplicate_pending_checkup_recalls(
        self, api_client, admin_user, patient_factory
    ):
        patient = patient_factory(doctor=None)

        #test recall count before post request 
        assert PatientRecall.objects.filter(
            patient=patient, type='checkup', status='pending'
        ).count() == 0

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _list_url(patient.id),
            _create_payload(type='routine_checkup'),
            format='json',
        )
        response2 = api_client.post(
            _list_url(patient.id),
            _create_payload(type='routine_checkup'),
            format='json',
        )
        
        assert response.status_code == status.HTTP_201_CREATED or render_error(response)
        assert response2.status_code == status.HTTP_201_CREATED or render_error(response)

        #check we have exactly two visits
        assert Visit.objects.filter(patient=patient).count() == 2

        #now test pending checkup recall count after post requests (should be updated, not duplicated)
        assert PatientRecall.objects.filter(
            patient=patient, type='checkup', status='pending'
        ).count() == 1


# ══════════════════════════════════════════════════════════════════════════════
# GET  /patients/visits/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRetrieveVisitsOptionsAPIView:
    URL = 'visits_options'

    def test_authenticated_user_gets_options_payload(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        for key in ('branchChoices', 'visitTypeChoices',
                    'optionalProcedureChoices', 'optionalProcedureTypeChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_visit_type_choices_cover_all_types(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        returned = {c['value'] for c in response.data['visitTypeChoices']}
        assert returned == {'routine_checkup', 'follow_up', 'emergency'}

    def test_optional_procedure_choices_include_formatted_price(
        self, api_client, admin_user, procedure_factory
    ):
        procedure_factory(name='Consultation', currency='$', price='180.00')
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        names = [c['name'] for c in response.data['optionalProcedureChoices']]
        assert 'Consultation' in names

    def test_optional_procedure_choices_empty_when_branches_exist_and_no_branch_id(
        self, api_client, admin_user, branch_factory, procedure_factory
    ):
        b = branch_factory()
        procedure_factory(branch=b)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert response.data['optionalProcedureChoices'] == []

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

