import uuid
import pytest
from django.urls import reverse
from rest_framework import status
from clinic.models import WorkingDaysLookUp
from datetime import date, time as time_type, timedelta
from users.models import DoctorSchedule, DoctorScheduleException


# ─────────────────────────────────────────────────────────────────────────────
# URL helpers
# ─────────────────────────────────────────────────────────────────────────────

def _schedule_url(doctor_id):
    return reverse('CRUD_doctor_schedule', kwargs={'doctorId': doctor_id})

def _exception_create_url(doctor_id):
    return reverse('create_schedule_exception', kwargs={'doctorId': doctor_id})

def _exception_delete_url(doctor_id, date_str):
    return reverse('delete_schedule_exception', kwargs={'doctorId': doctor_id, 'date': date_str})


# ─────────────────────────────────────────────────────────────────────────────
# Factories
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def schedule_factory():
    """Creates a DoctorSchedule directly in the ORM. Requires a doctor= kwarg."""
    def _create(doctor, **overrides):
        defaults = {
            'doctor':      doctor,
            'workingDays': [0, 1, 2, 3, 4],
            'startTime':   time_type(9, 0),
            'endTime':     time_type(17, 0),
        }
        defaults.update(overrides)
        return DoctorSchedule.objects.create(**defaults)

    return _create


@pytest.fixture
def exception_factory():
    """Creates a DoctorScheduleException. Pass schedule= and optionally date= / type=."""
    def _create(schedule, **overrides):
        defaults = {
            'schedule': schedule,
            'date':     date.today() + timedelta(days=7),
            'type':     'off',
        }
        defaults.update(overrides)
        return DoctorScheduleException.objects.create(**defaults)

    return _create


# ─────────────────────────────────────────────────────────────────────────────
# Payload helpers
# ─────────────────────────────────────────────────────────────────────────────

def _schedule_payload(**overrides):
    base = {
        'workingDays': [0, 1, 2, 3, 4],
        'startTime':   '09:00:00',
        'endTime':     '17:00:00',
    }
    base.update(overrides)
    return base

def _exception_payload(**overrides):
    base = {
        'date': str(date.today() + timedelta(days=14)),
        'type': 'off',
    }
    base.update(overrides)
    return base



# ══════════════════════════════════════════════════════════════════════════════
# GET  /doctor-schedules/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestListDoctorsSchedulesAPIView:
    URL = 'list_doctors_schedules'

    def test_admin_can_list_all_schedules(
        self, api_client, admin_user, dentist_user, other_dentist_user, schedule_factory
    ):
        s1 = schedule_factory(doctor=dentist_user)
        s2 = schedule_factory(doctor=other_dentist_user)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        ids = [str(s['id']) for s in response.data['data']]
        assert str(s1.id) in ids
        assert str(s2.id) in ids

    def test_list_response_has_paginated_structure(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        assert response.data['success'] is True
        for key in ('data', 'pagination', 'links', 'metadata'):
            assert key in response.data, f"Missing key: {key}"

    def test_user_with_view_doctor_schedules_can_list(
        self, api_client, receptionist_user, dentist_user, schedule_factory
    ):
        """All default roles carry 'view.doctorSchedules'."""
        schedule = schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        assert str(schedule.id) in [str(s['id']) for s in response.data['data']]

    def test_user_without_view_permission_gets_403(
        self, api_client, user_factory
    ):
        """Strip userPermissions to simulate a user with no view.doctorSchedules."""
        user = user_factory(role='receptionist')
        user.userPermissions = []
        user.save(update_fields=['userPermissions'])

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_schedules_of_soft_deleted_doctors_are_excluded(
        self, api_client, admin_user, user_factory, schedule_factory
    ):
        """DoctorSchedulesManager filters doctor__is_deleted=False."""
        ghost_doctor = user_factory(role='dentist')
        s = schedule_factory(doctor=ghost_doctor)

        ghost_doctor.is_deleted = True
        ghost_doctor.save(update_fields=['is_deleted'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert str(s.id) not in [str(x['id']) for x in response.data['data']]

    def test_unauthenticated_gets_401(self, api_client):
        assert api_client.get(reverse(self.URL)).status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# GET | POST | PUT | DELETE  /doctor-schedules/<doctorId>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCRUDDoctorScheduleAPIView:

    # ── RETRIEVE ──────────────────────────────────────────────────────────────

    def test_admin_can_retrieve_schedule_by_doctor_id(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule = schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_schedule_url(dentist_user.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['id'] == str(schedule.id)

    def test_retrieve_response_is_wrapped_with_metadata(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        """DoctorScheduleSerializer inherits UserPermissionsMixin → metadata on GET."""
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_schedule_url(dentist_user.id))

        assert response.data.get('success') is True
        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_retrieve_response_includes_nested_exceptions(
        self, api_client, admin_user, dentist_user, schedule_factory, exception_factory
    ):
        schedule = schedule_factory(doctor=dentist_user)
        exception_factory(schedule=schedule)
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(_schedule_url(dentist_user.id))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']['exceptions']) == 1

    def test_nonexistent_doctor_returns_404(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        assert api_client.get(_schedule_url(uuid.uuid4())).status_code == status.HTTP_404_NOT_FOUND

    def test_doctor_without_schedule_returns_404(
        self, api_client, admin_user, dentist_user
    ):
        """No DoctorSchedule for this doctor → get_object raises 404."""
        api_client.force_authenticate(user=admin_user)
        assert api_client.get(_schedule_url(dentist_user.id)).status_code == status.HTTP_404_NOT_FOUND

    def test_receptionist_can_retrieve_schedule(
        self, api_client, receptionist_user, dentist_user, schedule_factory
    ):
        """GET uses SystemUserPermissions; receptionist has view.doctorSchedules."""
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=receptionist_user)
        assert api_client.get(_schedule_url(dentist_user.id)).status_code == status.HTTP_200_OK

    # ── CREATE (POST) ─────────────────────────────────────────────────────────

    def test_admin_can_create_schedule_for_doctor(
        self, api_client, admin_user, dentist_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _schedule_url(dentist_user.id), _schedule_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert DoctorSchedule.objects.filter(doctor=dentist_user).exists()

    def test_dentist_can_create_own_schedule(self, api_client, user_factory):
        """A dentist may POST to their own doctorId."""
        doctor = user_factory(role='dentist')
        api_client.force_authenticate(user=doctor)
        response = api_client.post(
            _schedule_url(doctor.id), _schedule_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_dentist_cannot_create_schedule_for_other_doctor(
        self, api_client, dentist_user, other_dentist_user
    ):
        """view.create() raises PermissionDenied when requester != target doctor."""
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _schedule_url(other_dentist_user.id), _schedule_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_receptionist_cannot_create_schedule(
        self, api_client, receptionist_user, dentist_user
    ):
        """DoctorSchedulePermissions: only admin or dentist may POST."""
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            _schedule_url(dentist_user.id), _schedule_payload(), format='json'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_creating_duplicate_schedule_returns_400(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule_factory(doctor=dentist_user)   # already exists
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _schedule_url(dentist_user.id), _schedule_payload(), format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_exceptions_bulk_creates_them(
        self, api_client, admin_user, dentist_user
    ):
        exc_date = str(date.today() + timedelta(days=30))
        payload = {
            **_schedule_payload(),
            'exceptions': [{'date': exc_date, 'type': 'vacation', 'note': 'Summer leave'}],
        }
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _schedule_url(dentist_user.id), payload, format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        schedule = DoctorSchedule.objects.get(doctor=dentist_user)
        assert schedule.exceptions.filter(date=exc_date, type='vacation').exists()

    def test_create_response_is_wrapped(
        self, api_client, admin_user, dentist_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _schedule_url(dentist_user.id), _schedule_payload(), format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data.get('success') is True
        assert 'data' in response.data

    def test_working_days_deduplication_on_create(
        self, api_client, admin_user, dentist_user
    ):
        api_client.force_authenticate(user=admin_user)
        api_client.post(
            _schedule_url(dentist_user.id),
            _schedule_payload(workingDays=[1, 1, 3, 3, 5]),
            format='json',
        )

        schedule = DoctorSchedule.objects.get(doctor=dentist_user)
        assert schedule.workingDays == sorted({1, 3, 5})

    def test_create_with_empty_working_days_returns_400(
        self, api_client, admin_user, dentist_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _schedule_url(dentist_user.id),
            _schedule_payload(workingDays=[]),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_method_not_allowed(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        """PATCH excluded from http_method_names → 405."""
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            _schedule_url(dentist_user.id), {'startTime': '10:00:00'}, format='json'
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # ── UPDATE (PUT) ──────────────────────────────────────────────────────────

    def test_admin_can_update_schedule(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _schedule_url(dentist_user.id),
            _schedule_payload(startTime='10:00:00', workingDays=[1, 2, 3]),
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        schedule = DoctorSchedule.objects.get(doctor=dentist_user)
        assert schedule.workingDays == [1, 2, 3]

    def test_dentist_can_update_own_schedule(
        self, api_client, user_factory, schedule_factory
    ):
        doctor = user_factory(role='dentist')
        schedule_factory(doctor=doctor)
        api_client.force_authenticate(user=doctor)
        response = api_client.put(
            _schedule_url(doctor.id),
            _schedule_payload(endTime='18:00:00'),
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

    def test_dentist_cannot_update_other_doctors_schedule(
        self, api_client, dentist_user, other_dentist_user, schedule_factory
    ):
        """has_object_permission: schedule.doctor must equal request.user."""
        schedule_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.put(
            _schedule_url(other_dentist_user.id),
            _schedule_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_exceptions_replaces_all_existing(
        self, api_client, admin_user, dentist_user, schedule_factory, exception_factory
    ):
        """serializer.update(): if 'exceptions' provided → delete + recreate."""
        schedule = schedule_factory(doctor=dentist_user)
        exception_factory(schedule=schedule, type='off')

        new_date = str(date.today() + timedelta(days=60))
        api_client.force_authenticate(user=admin_user)
        api_client.put(
            _schedule_url(dentist_user.id),
            {**_schedule_payload(), 'exceptions': [{'date': new_date, 'type': 'conference'}]},
            format='json',
        )

        schedule.refresh_from_db()
        assert schedule.exceptions.count() == 1
        assert str(schedule.exceptions.first().date) == new_date
        assert schedule.exceptions.first().type == 'conference'

    def test_update_without_exceptions_key_preserves_existing(
        self, api_client, admin_user, dentist_user, schedule_factory, exception_factory
    ):
        """If 'exceptions' absent from PUT payload, existing exceptions are untouched."""
        schedule = schedule_factory(doctor=dentist_user)
        exception_factory(schedule=schedule)

        api_client.force_authenticate(user=admin_user)
        api_client.put(
            _schedule_url(dentist_user.id),
            _schedule_payload(startTime='08:00:00'),   #o 'exceptions' key
            format='json',
        )

        schedule.refresh_from_db()
        assert schedule.exceptions.count() == 1   # still there

    def test_update_response_is_wrapped(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.put(
            _schedule_url(dentist_user.id),
            _schedule_payload(workingDays=[0, 1, 2]),
            format='json',
        )

        assert response.data.get('success') is True
        assert 'data' in response.data

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_schedule(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule = schedule_factory(doctor=dentist_user)
        sid = schedule.id
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_schedule_url(dentist_user.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DoctorSchedule.objects.filter(id=sid).exists()

    def test_dentist_can_delete_own_schedule(
        self, api_client, user_factory, schedule_factory
    ):
        doctor = user_factory(role='dentist')
        schedule_factory(doctor=doctor)
        api_client.force_authenticate(user=doctor)
        assert api_client.delete(_schedule_url(doctor.id)).status_code == status.HTTP_204_NO_CONTENT

    def test_dentist_cannot_delete_other_doctors_schedule(
        self, api_client, dentist_user, other_dentist_user, schedule_factory
    ):
        schedule_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        assert api_client.delete(
            _schedule_url(other_dentist_user.id)
        ).status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_access_any_method(
        self, api_client, dentist_user, schedule_factory
    ):
        schedule_factory(doctor=dentist_user)
        assert api_client.get(_schedule_url(dentist_user.id)).status_code == status.HTTP_401_UNAUTHORIZED
        assert api_client.post(_schedule_url(dentist_user.id), {}).status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# POST  /doctor-schedule/<doctorId>/exceptions/
#ELETE  /doctor-schedule/<doctorId>/exceptions/<date>/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestScheduleExceptionsAPIView:

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_admin_can_create_exception(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule_factory(doctor=dentist_user)
        exc_date = str(date.today() + timedelta(days=14))

        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _exception_create_url(dentist_user.id),
            {'date': exc_date, 'type': 'off'},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert DoctorScheduleException.objects.filter(
            schedule__doctor=dentist_user, date=exc_date
        ).exists()

    def test_dentist_can_create_own_exception(
        self, api_client, user_factory, schedule_factory
    ):
        doctor = user_factory(role='dentist')
        schedule_factory(doctor=doctor)
        api_client.force_authenticate(user=doctor)
        response = api_client.post(
            _exception_create_url(doctor.id),
            _exception_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_dentist_cannot_create_exception_for_other_doctor(
        self, api_client, dentist_user, other_dentist_user, schedule_factory
    ):
        schedule_factory(doctor=other_dentist_user)
        api_client.force_authenticate(user=dentist_user)
        response = api_client.post(
            _exception_create_url(other_dentist_user.id),
            _exception_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_receptionist_cannot_create_exception(
        self, api_client, receptionist_user, dentist_user, schedule_factory
    ):
        """DoctorSchedulePermissions: only admin or dentist allowed."""
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.post(
            _exception_create_url(dentist_user.id),
            _exception_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_exception_without_schedule_returns_404(
        self, api_client, admin_user, dentist_user
    ):
        """get_serializer_context uses get_object_or_404 on the schedule."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _exception_create_url(dentist_user.id),
            _exception_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_exception_with_invalid_doctor_returns_404(
        self, api_client, admin_user
    ):
        api_client.force_authenticate(user=admin_user)
        response = api_client.post(
            _exception_create_url(uuid.uuid4()),
            _exception_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_admin_can_delete_exception(
        self, api_client, admin_user, dentist_user, schedule_factory, exception_factory
    ):
        schedule = schedule_factory(doctor=dentist_user)
        exc_date = date.today() + timedelta(days=14)
        exception_factory(schedule=schedule, date=exc_date)

        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(_exception_delete_url(dentist_user.id, str(exc_date)))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DoctorScheduleException.objects.filter(
            schedule__doctor=dentist_user, date=exc_date
        ).exists()

    def test_dentist_can_delete_own_exception(
        self, api_client, user_factory, schedule_factory, exception_factory
    ):
        doctor = user_factory(role='dentist')
        schedule = schedule_factory(doctor=doctor)
        exc_date = date.today() + timedelta(days=10)
        exception_factory(schedule=schedule, date=exc_date)

        api_client.force_authenticate(user=doctor)
        response = api_client.delete(_exception_delete_url(doctor.id, str(exc_date)))

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_dentist_cannot_delete_other_doctors_exception(
        self, api_client, dentist_user, other_dentist_user, schedule_factory, exception_factory
    ):
        schedule = schedule_factory(doctor=other_dentist_user)
        exc_date = date.today() + timedelta(days=10)
        exception_factory(schedule=schedule, date=exc_date)

        api_client.force_authenticate(user=dentist_user)
        response = api_client.delete(
            _exception_delete_url(other_dentist_user.id, str(exc_date))
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_date_format_returns_400(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        """DeleteScheduleExceptionAPIView.get_object() raises 400 on bad date format."""
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(
            _exception_delete_url(dentist_user.id, 'not-a-date')
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_date_returns_404(
        self, api_client, admin_user, dentist_user, schedule_factory
    ):
        schedule_factory(doctor=dentist_user)
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(
            _exception_delete_url(dentist_user.id, '2099-12-31')   #o exception on this date
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════════════
# GET  /doctor-schedules/options/
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDoctorSchedulesOptionsAPIView:
    """
    Plain generics.GenericAPIView + BranchToSerializerMixin.
    ResponseMixin is NOT applied — response is a bare dict.
    """
    URL = 'doctor_schedules_options'

    def test_authenticated_user_gets_options_payload(self, api_client, receptionist_user):
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK
        for key in ('branchChoices', 'doctorChoices', 'weekDaysChoices', 'exceptionTypeChoices'):
            assert key in response.data, f"Missing key: {key}"

    def test_response_is_not_wrapped(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))
        assert 'success' not in response.data

    def test_week_days_choices_cover_all_seven_days(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['weekDaysChoices']}
        expected = set(WorkingDaysLookUp.values)
        assert returned == expected

    def test_exception_type_choices_cover_all_types(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        returned = {c['value'] for c in response.data['exceptionTypeChoices']}
        expected = {c.value for c in DoctorScheduleException.ExceptionTypeChoices}
        assert returned == expected

    def test_doctor_choices_include_all_dentists_when_no_branch_id(
        self, api_client, admin_user, dentist_user
    ):
        """
        get_doctorChoices without branchId returns ALL admin+dentist users,
        unlike waiting-room which returns [] when branches exist.
        """
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        doctor_ids = {str(c['doctorId']) for c in response.data['doctorChoices']}
        assert str(dentist_user.id) in doctor_ids

    def test_doctor_choices_filtered_by_branch_id(
        self, api_client, admin_user, dentist_user, branch_factory
    ):
        """get_doctorChoices with branchId filters by User.branch_id."""
        b = branch_factory()
        dentist_user.branch = b
        dentist_user.save(update_fields=['branch', 'updatedAt'])

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(b.id)})

        doctor_ids = {str(c['doctorId']) for c in response.data['doctorChoices']}
        assert str(dentist_user.id) in doctor_ids

    def test_invalid_branch_id_returns_400(self, api_client, admin_user):
        """BranchToSerializerMixin validates branchId exists."""
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(uuid.uuid4())})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, api_client):
        assert api_client.get(reverse(self.URL)).status_code == status.HTTP_401_UNAUTHORIZED
