import os
import itertools
from io import BytesIO
from decimal import Decimal
from datetime import time, timedelta


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DentalTech.settings.dev')
os.environ.setdefault('DEV_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('EMAIL_PORT', '1025')


import django
import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image


def pytest_configure():
    """Configure Django settings for pytest."""
    if not settings.configured:
        django.setup()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture(autouse=True)
def test_settings(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / 'media'
    settings.ENABLE_AUTOMATED_REMINDERS = False
    settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN = 'test-webhook-token'
    settings.WHATSAPP_TEMPLATE_LANGUAGE = 'en_US'
    settings.WHATSAPP_CUSTOM_MESSAGE_TEMPLATE_EN = 'custom_message_english'
    settings.WHATSAPP_CUSTOM_TEMPLATE_EN = 'custom_message_english'
    settings.CLINIC_NAME = 'Test Clinic'
    return settings


@pytest.fixture
def user_factory():
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    counter = itertools.count(1)

    def create_user(role='admin', password='Password123', **overrides):
        index = next(counter)
        defaults = {
            'email': f'user{index}@test.com',
            'name': f'{role} User {index}',
            'role': role,
        }
        defaults.update(overrides)
        return user_model.objects.create_user(password=password, **defaults)

    return create_user


@pytest.fixture
def admin_user(user_factory):
    return user_factory(role='admin', email='admin@test.com', name='Admin User')


@pytest.fixture
def dentist_user(user_factory):
    return user_factory(role='dentist', email='dentist@test.com', name='Dentist User')


@pytest.fixture
def other_dentist_user(user_factory):
    return user_factory(role='dentist', email='other.dentist@test.com', name='Other Dentist')


@pytest.fixture
def receptionist_user(user_factory):
    return user_factory(
        role='receptionist',
        email='receptionist@test.com',
        name='Receptionist User',
    )

@pytest.fixture
def assistant_user(user_factory):
    return user_factory(role='assistant', email='assistant@test.com', name='Assistant User')

@pytest.fixture
def accountant_user(user_factory):
    return user_factory(role='accountant', email='accountant@test.com', name='Accountant User')


@pytest.fixture
def branch_factory():
    from clinic.models import Branch

    counter = itertools.count(1)

    def _create(**overrides):
        idx = next(counter)
        defaults = {
            'name': f'Test Branch {idx}',
            'phone': f'+201000000{idx:03d}',
            'workingDays': [0, 1, 2, 3, 4],
            'openTime': time(9, 0),
            'closeTime': time(17, 0),
        }
        defaults.update(overrides)
        return Branch.objects.create(**defaults)

    return _create

@pytest.fixture
def branch(branch_factory):
    return branch_factory()


@pytest.fixture
def patient_factory():
    from patients.models import Patient

    counter = itertools.count(1)

    def create_patient(**overrides):
        index = next(counter)
        defaults = {
            'name': f'Patient {index}',
            'age': 30,
            'gender': 'male',
            'email': f'patient{index}@example.com',
            'countryCode': '20',
            'phone': f'0101234{index:04d}',
        }
        defaults.update(overrides)
        return Patient.objects.create(**defaults)

    return create_patient


@pytest.fixture
def procedure_factory():
    from clinic.models import Procedure

    counter = itertools.count(1)

    def create_procedure(**overrides):
        index = next(counter)
        defaults = {
            'name': f'Procedure {index}',
            'category': Procedure.ProcedureCategory.CheckUp,
            'duration': 30,
            'price': Decimal('150.00'),
            'currency': '$',
        }
        defaults.update(overrides)
        return Procedure.objects.create(**defaults)

    return create_procedure


@pytest.fixture
def appointment_factory():
    from patients.models import Appointment

    counter = itertools.count(1)

    def create_appointment(patient, doctor, procedure, **overrides):
        index = next(counter)
        defaults = {
            'patient': patient,
            'doctor': doctor,
            'procedure': procedure,
            'date': timezone.localdate() + timedelta(days=1),
            'startTime': time(9 + (index - 1), 0),
            'endTime': time(10 + (index - 1), 0),
            'type': procedure.name,
            'room': f'Room {index}',
            'status': 'pending'
        }
        defaults.update(overrides)
        return Appointment.objects.create(**defaults)

    return create_appointment


@pytest.fixture
def visit_factory():
    from patients.models import Visit

    counter = itertools.count(1)

    def create_visit(patient, doctor, **overrides):
        index = next(counter)
        defaults = {
            'patient': patient,
            'doctor': doctor,
            'date': timezone.localdate(),
            'type': 'follow_up',
            'procedures': [f'Procedure {index}'],
            'cost': Decimal('200.00'),
            'paid': Decimal('150.00'),
            'currency': '$',
            'notes': f'Visit notes {index}',
        }
        defaults.update(overrides)
        return Visit.objects.create(**defaults)

    return create_visit


@pytest.fixture
def treatment_plan_factory():
    from patients.models import TreatmentPlan, TreatmentPlanItem

    def create_treatment_plan(
        patient,
        procedure,
        doctor=None,
        treatment_items=None,
        **overrides,
    ):
        # TreatmentPlan model fields (current): title, status, currency, totalCost,
        # installmentMonths, sessions
        treatment_plan = TreatmentPlan.objects.create(
            patient=patient,
            doctor=doctor,
            title=overrides.pop('title', 'Treatment Plan'),
            status=overrides.pop('status', 'active'),
            currency=overrides.pop('currency', '$'),
            totalCost=overrides.pop('totalCost', Decimal('0')),
            sessions=overrides.pop('sessions', None),
            **overrides,
        )

        items = treatment_items or [
            {
                'procedure': procedure,
                'toothNumber': '11',
                'price': Decimal('120.00'),
                'session': 1,
                'status': 'pending',
                'notes': None,
            }
        ]

        created_items = []
        total_cost = 0
        for item in items:
            total_cost += float(item['price'])
            created_items.append(
                TreatmentPlanItem(
                    treatmentPlan=treatment_plan,
                    procedure=item['procedure'],
                    toothNumber=item.get('toothNumber'),
                    price=item['price'],
                    session=item.get('session'),
                    status=item.get('status', 'pending'),
                    notes=item.get('notes'),
                )
            )

        TreatmentPlanItem.objects.bulk_create(created_items)
        treatment_plan.totalCost = Decimal(f'{total_cost:.2f}')
        treatment_plan.save(update_fields=['totalCost'])
        return treatment_plan

    return create_treatment_plan

@pytest.fixture
def png_file():
    image_bytes = BytesIO()
    Image.new('RGB', (1, 1), color='white').save(image_bytes, format='PNG')
    image_bytes.seek(0)
    return SimpleUploadedFile(
        'xray.png',
        image_bytes.read(),
        content_type='image/png',
    )

@pytest.fixture
def pdf_file():
    return SimpleUploadedFile(
        'document.pdf',
        b'%PDF-1.4 fake pdf content for testing',
        content_type='application/pdf',
    )

@pytest.fixture
def inventory_factory():
    from clinic.models import Inventory

    counter = itertools.count(1)

    def create_inventory_item(**overrides):
        index = next(counter)
        defaults = {
            'name': f'Inventory Item {index}',
            'category': 'Consumables',
            'currentStock': 10,
            'minStock': 5,
            'unit': 'pcs',
            'supplier': 'Acme Supplies',
            'lastOrdered': timezone.localdate(),
        }
        defaults.update(overrides)
        return Inventory.objects.create(**defaults)

    return create_inventory_item


@pytest.fixture
def bill_factory(patient_factory, dentist_user, visit_factory):
    """
    Creates Bill instances via the ORM with a default patient, visit, and amounts.
    M2M visits are set after creation, which fires the m2m_changed signal and
    updates visit.cost automatically.
    """

    from finances.models import Bill

    def _create(**overrides):
        patient = overrides.pop('patient', None) or patient_factory()
        visits = overrides.pop('visits', None)
        if visits is None:
            visits = [visit_factory(patient=patient, doctor=dentist_user)]

        defaults = {
            'patient':     patient,
            'description': 'Test Bill',
            'subtotal':    Decimal('200.00'),
            'totalAmount': Decimal('200.00'),
            'discount':    Decimal('0.00'),
            'currency':    '$',
        }
        defaults.update(overrides)
        bill = Bill.objects.create(**defaults)
        bill.visits.set(visits)
        return bill

    return _create


@pytest.fixture
def plan_bill_factory():
    from finances.models import Bill

    def _create(plan, **overrides):
        defaults = {
            'patient': plan.treatment.patient, 'treatment': plan.treatment, 'installmentPlan': plan,
            'branch': plan.branch, 'description': 'Installment plan bill',
            'subtotal': plan.totalAmount, 'totalAmount': plan.totalAmount, 'currency': plan.currency,
        }
        defaults.update(overrides)
        return Bill.objects.create(**defaults)

    return _create


@pytest.fixture
def installment_plan_factory(treatment_plan_factory, patient_factory, procedure_factory):
    from finances.models import InstallmentPlan, Installment

    def _create(treatment=None, months=3, down_payment=Decimal('0'), **overrides):
        treatment = treatment or treatment_plan_factory(
            patient=patient_factory(), procedure=procedure_factory()
        )
        total = treatment.totalCost
        start = timezone.localdate()
        plan = InstallmentPlan.objects.create(
            treatment=treatment,
            branch=treatment.patient.branch,
            installmentMonths=months,
            startDate=start,
            totalAmount=total,
            currency=treatment.currency,
            downPayment=down_payment,
            **overrides,
        )
        base = (total / months).quantize(Decimal('0.01'))
        for seq in range(1, months + 1):
            Installment.objects.create(
                installmentPlan=plan,
                amount=total - base * (months - 1) if seq == months else base,
                sequence=seq,
                dueDate=start + timedelta(days=30 * seq),
                type='installment',
            )
        return plan

    return _create


@pytest.fixture
def transaction_factory(bill_factory):
    """
    Creates Transaction instances using an existing or new Bill.
    Patient and visit are derived from the bill (mirrors validate() logic).
    post_save signal fires automatically, updating bill.totalPaid and
    visit.paid.
    """
    from finances.models import Transaction

    def _create(**overrides):
        bill = overrides.pop('bill',    None) or bill_factory()
        patient = overrides.pop('patient', None) or bill.patient
        visit = overrides.pop('visit',   None) or bill.visits.first()

        defaults = {
            'bill':     bill,
            'patient':  patient,
            'visit':    visit,
            'date':     timezone.localdate(timezone.now()),
            'amount':   Decimal('150.00'),
            'currency': '$',
        }
        
        defaults.update(overrides)
        return Transaction.objects.create(**defaults)

    return _create

@pytest.fixture
def refund_transaction(transaction_factory):
    def _refund(transaction=None, reason='Test refund', **overrides):
        txn = transaction or transaction_factory(**overrides)
        txn.status = 'refunded'
        txn.refundReason = reason
        txn.save(update_fields=['status', 'refundReason'])
        return txn
    return _refund

@pytest.fixture
def deposit_factory(treatment_plan_factory, patient_factory, procedure_factory):
    from finances.models import Transaction
    
    def _create(treatment=None, amount=Decimal('500.00'), **overrides):
        treatment = treatment or treatment_plan_factory(
            patient=patient_factory(), procedure=procedure_factory(), totalCost=amount
        )
        return Transaction.autogenerate_deposit_after_reducing_costs_below_paid(
            amount=amount, treatment=treatment, **overrides
        )
    return _create


@pytest.fixture
def coverage_factory(insurance_provider_factory):
    """Attaches a provider to the patient's auto-created coverage row."""
    def _setup(patient, provider=None, **coverage_fields):
        provider = provider or insurance_provider_factory()
        coverage = patient.patient_insurance
        coverage.provider = provider
        for key, value in {'eligibilityStatus': 'active', 'deductibleMet': True, **coverage_fields}.items():
            setattr(coverage, key, value)
        coverage.save()
        return coverage
    return _setup


@pytest.fixture
def insurance_provider_factory():
    from finances.models import InsuranceProvider

    counter = itertools.count(1)

    def _create(**overrides):
        idx = next(counter)
        defaults = {
            'name':            f'Insurance Provider {idx}',
            'tier':            'direct',
            'contact':         f'contact{idx}@provider.com',
            'coveragePercent': 80,
            'annualMax':       Decimal('10000.00'),
            'currency':        '$',
        }
        defaults.update(overrides)
        return InsuranceProvider.objects.create(**defaults)

    return _create
