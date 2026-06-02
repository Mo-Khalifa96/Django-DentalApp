import itertools
import os
from datetime import time, timedelta
from io import BytesIO


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
def patient_factory():
    from patients.models import Patient

    counter = itertools.count(1)

    def create_patient(**overrides):
        index = next(counter)
        defaults = {
            'name': f'Patient {index}',
            'age': 30,
            'gender': 'Male',
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
            'price': '150.00',
            'currency': '$',
        }
        defaults.update(overrides)
        return Procedure.objects.create(**defaults)

    return create_procedure


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
            'status': 'pending',
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
            'type': f'Visit Type {index}',
            'procedures': [f'Procedure {index}'],
            'cost': '200.00',
            'paid': '150.00',
            'currency': '$',
            'notes': f'Visit notes {index}',
        }
        defaults.update(overrides)
        return Visit.objects.create(**defaults)

    return create_visit


@pytest.fixture
def treatment_plan_factory():
    from patients.models import TreatmentPlan, TreatmentPlanItem

    def create_treatment_plan(patient, procedure, doctor=None, items=None, **overrides):
        treatment_plan = TreatmentPlan.objects.create(
            patient=patient,
            doctor=doctor,
            totalCost=overrides.pop('totalCost', '0.00'),
            currency=overrides.pop('currency', '$'),
            paymentPlan=overrides.pop('paymentPlan', None),
            notes=overrides.pop('notes', 'Treatment notes'),
            status=overrides.pop('status', 'pending'),
            **overrides,
        )

        items = items or [
            {
                'procedure': procedure,
                'toothNumber': '11',
                'price': '120.00',
                'duration': 30,
                'completed': False,
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
                    duration=item.get('duration'),
                    completed=item.get('completed', False),
                )
            )

        TreatmentPlanItem.objects.bulk_create(created_items)
        treatment_plan.totalCost = f'{total_cost:.2f}'
        treatment_plan.save(update_fields=['totalCost'])
        return treatment_plan

    return create_treatment_plan


@pytest.fixture
def message_factory():
    from services.models import Message

    def create_message(patient, appointment, **overrides):
        defaults = {
            'message': 'Appointment reminder',
            'status': 'queued',
        }
        defaults.update(overrides)
        return Message.objects.create(
            patient=patient,
            appointment=appointment,
            **defaults,
        )

    return create_message


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
