import pytest
from decimal import Decimal
from .utils import render_error
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from datetime import date, timedelta

pytestmark = pytest.mark.django_db


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get(api_client, **qp):
    return api_client.get(reverse('dashboard_stats'), qp or None)

def _data(response):
    """Return the nested data dict from the wrapped response."""
    return response.data['data']


@pytest.mark.django_db
class TestDashboardStatsAPI:
    URL = 'dashboard_stats'

    # ══════════════════════════════════════════════════════════════════════════════
    # Permissions
    # ══════════════════════════════════════════════════════════════════════════════

    def test_unauthenticated_returns_401(self, api_client):
        response = _get(api_client)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)

    def test_admin_gets_full_stats(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = _get(api_client)

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['success'] == True
        assert 'data' in response.data
        assert 'metadata' in response.data

    def test_user_with_clinical_analytics_gets_stats(
        self, api_client, receptionist_user
    ):
        """receptionist has 'view.clinicalAnalytics' by default."""
        
        api_client.force_authenticate(user=receptionist_user)
        response = _get(api_client)

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'data' in response.data

    def test_user_without_clinical_analytics_gets_wrapped_response_with_null_values(
        self, api_client, user_factory
    ):
        user = user_factory(role='receptionist')
        user.userPermissions = []   #strip all permissions
        user.save(update_fields=['userPermissions'])

        api_client.force_authenticate(user=user)
        response = _get(api_client)

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert response.data['success'] == True
        assert 'data' in response.data
        assert 'metadata' in response.data
        response_data = response.data['data']
        for field in response_data.keys():
            assert response_data[field] == None


    # ══════════════════════════════════════════════════════════════════════════════
    # Response structure
    # ══════════════════════════════════════════════════════════════════════════════

    def test_response_is_wrapped_by_response_mixin(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = _get(api_client)

        assert response.data.get('success') is True
        assert 'data' in response.data
        assert 'metadata' in response.data
        assert 'userPermissions' in response.data['metadata']

    def test_data_contains_all_expected_fields(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        for field in ('patientsTotal', 'patientsNew', 'appointmentsCount',
                      'appointmentsCompleted', 'revenue', 'outstanding'):
            assert field in data, f"Missing field: {field}"

    def test_invalid_date_range_returns_400(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'dateRange': 'invalid'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST or render_error(response)


    # ══════════════════════════════════════════════════════════════════════════════
    # Financial data – Revenue and Outstanding
    # ══════════════════════════════════════════════════════════════════════════════

    def test_revenue_is_sum_of_transaction_amounts_not_visit_paid(
        self, api_client, admin_user, patient_factory, dentist_user,
        visit_factory, bill_factory, transaction_factory
    ):
        patient = patient_factory()
        visit   = visit_factory(patient=patient, doctor=dentist_user, paid='999.00')
        bill    = bill_factory(patient=patient, visits=[visit],
                               subtotal=Decimal('300.00'), totalAmount=Decimal('300.00'))
        transaction_factory(bill=bill, visit=visit, patient=patient, amount=Decimal('250.00'))

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['revenue'] == 250.0    # transaction amount
        assert data['revenue'] != 999.0    #ot visit.paid

    def test_outstanding_is_billed_minus_total_paid(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        """outstanding = SUM(Bill.totalAmount) - SUM(Transaction.amount)."""

        bill = bill_factory(subtotal=Decimal('300.00'), totalAmount=Decimal('300.00'))
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=bill.patient, amount=Decimal('100.00'))

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['outstanding'] == pytest.approx(200.0, abs=0.01)

    def test_outstanding_zero_when_fully_paid(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        bill = bill_factory(subtotal=Decimal('200.00'), totalAmount=Decimal('200.00'))
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=bill.patient, amount=Decimal('200.00'))

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['outstanding'] == pytest.approx(0.0, abs=0.01)

    def test_revenue_and_outstanding_hidden_without_financial_analytics(
        self, api_client, receptionist_user
    ):
        """receptionist has view.clinicalAnalytics but NOT view.financialAnalytics."""

        api_client.force_authenticate(user=receptionist_user)
        data = _data(_get(api_client))

        assert 'revenue'     not in data
        assert 'outstanding' not in data

    def test_accountant_with_financial_analytics_sees_revenue_and_outstanding(
        self, api_client, user_factory
    ):
        """accountant has view.financialAnalytics by default."""

        accountant = user_factory(role='accountant')
        api_client.force_authenticate(user=accountant)
        data = _data(_get(api_client))

        assert 'revenue'     in data
        assert 'outstanding' in data

    def test_soft_deleted_bills_excluded_from_outstanding_calculation(
        self, api_client, admin_user, bill_factory
    ):
        """Bill.objects (used for outstanding) filters isDeleted=False."""

        bill = bill_factory(subtotal=Decimal('500.00'), totalAmount=Decimal('500.00'))
        bill.isDeleted = True
        bill.save(update_fields=['isDeleted'])

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        #deleted bill should not contribute to total_billed
        assert data['outstanding'] == pytest.approx(0.0, abs=0.01)


    # ══════════════════════════════════════════════════════════════════════════════
    # Date range filtering
    # ══════════════════════════════════════════════════════════════════════════════

    def test_revenue_defaults_to_current_month(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        """Default (no dateRange): revenue_filter uses current month."""
        bill = bill_factory()
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=bill.patient, amount=Decimal('180.00'))

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        #Transaction created today (current month) → counted
        assert data['revenue'] == 180.0

    def test_today_range_excludes_yesterdays_transaction(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        """dateRange=today uses Q(date__exact=today)."""

        bill       = bill_factory()
        yesterday  = date.today() - timedelta(days=1)
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=bill.patient, amount=Decimal('100.00'),
                            date=yesterday)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'dateRange': 'today'})
        data = _data(response)

        assert data['revenue'] == 0.0   # yesterday excluded

    def test_today_range_includes_todays_transaction(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        bill = bill_factory()
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=bill.patient, amount=Decimal('120.00'),
                            date=date.today())

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'dateRange': 'today'})
        data = _data(response)

        assert data['revenue'] == 120.0

    def test_week_range_excludes_transaction_from_previous_week(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        """dateRange=week: Q(date__range=(starting_saturday, ending_friday))."""

        bill      = bill_factory()
        two_weeks = date.today() - timedelta(days=14)
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=bill.patient, amount=Decimal('200.00'),
                            date=two_weeks)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL), {'dateRange': 'week'})
        data = _data(response)

        assert data['revenue'] == 0.0

    def test_month_range_behaviour_same_as_default(
        self, api_client, admin_user, bill_factory, transaction_factory
    ):
        """dateRange=month uses the same current-month filter as the default."""
        bill = bill_factory()
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=bill.patient, amount=Decimal('90.00'))

        api_client.force_authenticate(user=admin_user)
        default_rev = _data(_get(api_client))['revenue']
        month_rev   = _data(api_client.get(reverse(self.URL), {'dateRange': 'month'}))['revenue']

        assert default_rev == month_rev


    # ══════════════════════════════════════════════════════════════════════════════
    # Patient & appointment counts
    # ══════════════════════════════════════════════════════════════════════════════

    def test_patients_total_reflects_all_patients(
        self, api_client, admin_user, patient_factory
    ):
        p1 = patient_factory()
        p2 = patient_factory()

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['patientsTotal'] >= 2

    def test_patients_new_counts_patients_created_this_month(
        self, api_client, admin_user, patient_factory
    ):
        patient_factory()   #created now → this month

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['patientsNew'] >= 1

    def test_appointments_count_shows_todays_appointments_by_default(
        self, api_client, admin_user, patient_factory, dentist_user,
        procedure_factory, appointment_factory
    ):
        """Default appointmentsCount uses Q(date__exact=today)."""

        patient = patient_factory()
        proc    = procedure_factory()
        appointment_factory(patient=patient, doctor=dentist_user, procedure=proc,
                            date=date.today())

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['appointmentsCount'] >= 1

    def test_cancelled_appointments_excluded_from_all_counts(
        self, api_client, admin_user, patient_factory, dentist_user,
        procedure_factory, appointment_factory
    ):
        """Appointment queryset uses .exclude(status='cancelled')."""

        patient = patient_factory()
        proc    = procedure_factory()
        appointment_factory(patient=patient, doctor=dentist_user, procedure=proc,
                            date=date.today(), status='cancelled')

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['appointmentsCount'] == 0

    def test_appointments_completed_counts_completed_this_month(
        self, api_client, admin_user, patient_factory, dentist_user,
        procedure_factory, appointment_factory
    ):
        patient = patient_factory()
        proc    = procedure_factory()
        appointment_factory(patient=patient, doctor=dentist_user, procedure=proc,
                            date=date.today(), status='completed')

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['appointmentsCompleted'] >= 1


    # ══════════════════════════════════════════════════════════════════════════════
    # Branch filtering
    # ══════════════════════════════════════════════════════════════════════════════

    def test_admin_sees_all_data_across_branches_by_default(
        self, api_client, admin_user, patient_factory, branch_factory
    ):
        """Admin with no branchId QP → Q() filter → sees everything."""

        b1 = branch_factory()
        b2 = branch_factory()
        patient_factory(branch=b1)
        patient_factory(branch=b2)

        api_client.force_authenticate(user=admin_user)
        data = _data(_get(api_client))

        assert data['patientsTotal'] >= 2

    def test_non_admin_with_one_branch_sees_only_that_branch(
        self, api_client, user_factory, patient_factory, branch_factory,
        bill_factory, transaction_factory, dentist_user
    ):
        """
        For user with exactly one assigned branch, filter_by_branch yields
        Q(branch_id=user.branches.first().id).
        """

        b1 = branch_factory()
        b2 = branch_factory()
        accountant = user_factory(role='accountant')
        accountant.branches.set([b1])

        #b1 patient + bill + transaction
        p1   = patient_factory(branch=b1)
        bill = bill_factory(patient=p1,
                            subtotal=Decimal('200.00'), totalAmount=Decimal('200.00'),
                            branch=b1)
        transaction_factory(bill=bill, visit=bill.visits.first(),
                            patient=p1, amount=Decimal('150.00'), branch=b1)

        #patient + transaction
        p2    = patient_factory(branch=b2)
        bill2 = bill_factory(patient=p2, branch=b2)
        transaction_factory(bill=bill2, visit=bill2.visits.first(),
                            patient=p2, amount=Decimal('500.00'), branch=b2)

        api_client.force_authenticate(user=accountant)
        data = _data(_get(api_client))

        #Only b1 data should appear
        assert data['revenue'] == 150.0       #ot 650
        assert data['outstanding'] == pytest.approx(50.0, abs=0.01)   #0 - 150

    def test_branchId_qp_filters_dashboard_stats_for_non_admins(
        self, api_client, receptionist_user, branch
    ):
        receptionist_user.branches.add(branch)
        api_client.force_authenticate(user=receptionist_user)
        response = api_client.get(reverse(self.URL), {'branchId': str(branch.id)})

        assert response.status_code == status.HTTP_200_OK or render_error(response)


@pytest.mark.django_db
class TestDashboardAppointmentsTodayAPI:
    URL = 'dashboard_appointments_today'

    # ══════════════════════════════════════════════════════════════════════════════
    # GET  /dashboard/appointments-today/
    # ══════════════════════════════════════════════════════════════════════════════

    def test_dentist_sees_only_own_todays_appointments(
        self, api_client, dentist_user, other_dentist_user,
        patient_factory, procedure_factory, appointment_factory
    ):
        today = timezone.localdate()
        proc  = procedure_factory()
        visible = appointment_factory(patient=patient_factory(doctor=dentist_user),
                                      doctor=dentist_user, procedure=proc, date=today)
        appointment_factory(patient=patient_factory(doctor=other_dentist_user),
                            doctor=other_dentist_user, procedure=proc, date=today)
        #Tomorrow → excluded
        appointment_factory(patient=patient_factory(doctor=dentist_user),
                            doctor=dentist_user, procedure=proc,
                            date=today + timedelta(days=1))

        api_client.force_authenticate(user=dentist_user)
        response = api_client.get(reverse(self.URL))

        assert response.status_code == status.HTTP_200_OK or render_error(response)
        assert 'metadata' in response.data
        assert response.data['metadata']['userPermissions']['view.appointments'] is True
        assert [i['id'] for i in response.data['data']] == [str(visible.id)]

    def test_admin_sees_all_todays_appointments(
        self, api_client, admin_user, dentist_user, other_dentist_user,
        patient_factory, procedure_factory, appointment_factory
    ):
        today = timezone.localdate()
        proc  = procedure_factory()
        a1 = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                 procedure=proc, date=today)
        a2 = appointment_factory(patient=patient_factory(), doctor=other_dentist_user,
                                 procedure=proc, date=today)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(a1.id) in ids
        assert str(a2.id) in ids

    def test_only_todays_appointments_returned(
        self, api_client, admin_user, dentist_user, patient_factory,
        procedure_factory, appointment_factory
    ):
        """Filter is date__exact=today."""

        today     = timezone.localdate()
        proc      = procedure_factory()
        today_appt = appointment_factory(patient=patient_factory(), doctor=dentist_user,
                                         procedure=proc, date=today)
        appointment_factory(patient=patient_factory(), doctor=dentist_user,
                            procedure=proc, date=today + timedelta(days=1))

        api_client.force_authenticate(user=admin_user)
        response = api_client.get(reverse(self.URL))

        ids = [i['id'] for i in response.data['data']]
        assert str(today_appt.id) in ids
        assert len(ids) == 1

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(reverse(self.URL))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED or render_error(response)