import os
import sys
import random
import django
from faker import Faker
from pathlib import Path
from decimal import Decimal
from datetime import datetime, date, time, timedelta

#Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

#Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DentalTech.settings.dev')
django.setup()


from django.db.models import F
from django.db import transaction
from django.utils import timezone
from patients.validators import FDI_PERMANENT
from users.models import User, DoctorSchedule, DoctorScheduleException
from clinic.models import Branch, Procedure, Inventory, Lab, LabOrder, WaitingRoom, SterilizationLog
from patients.models import Patient, Visit, Appointment, TreatmentPlan, TreatmentPlanItem, PatientRecall


#Instantiate faker
faker = Faker()


# ── Helpers ────────────────────────────────────────────────────────────────────

COUNTRY_CODES = ['+20', '+966', '+971', '+974', '+965', '+973', '+968', '+1']

BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

COMMON_ALLERGIES = [
    'Penicillin', 'Amoxicillin', 'Latex', 'Aspirin', 'Ibuprofen',
    'Codeine', 'Sulfa drugs', 'Lidocaine', 'Epinephrine', 'Nickel'
]

INSURANCE_PROVIDERS = [
    'Bupa Arabia', 'AXA Cooperative', 'Tawuniya', 'Medgulf',
    'National Health Insurance', 'MetLife', 'Allianz', None, None, None  #some uninsured
]

FDI_TEETH_LIST = list(FDI_PERMANENT)

BRANCH_DATA = [
    {
        'name': 'Main Branch',
        'address': '12 Nile Corniche, Maadi, Cairo',
        'phone': '+20 2 2510 1234',
        'workingDays': [0, 1, 2, 3, 4, 5],
        'rooms': ['Chair 1', 'Chair 2', 'Chair 3', 'Consultation Room'],
        'openTime': time(9, 0),
        'closeTime': time(17, 0),
        'isMain': True,
        'color': '#0F766E',
    },
    {
        'name': 'Heliopolis Branch',
        'address': '55 El Ahram Street, Heliopolis, Cairo',
        'phone': '+20 2 2418 5678',
        'workingDays': [0, 1, 2, 3, 4],
        'rooms': ['Chair 1', 'Chair 2'],
        'openTime': time(10, 0),
        'closeTime': time(18, 0),
        'isMain': False,
        'color': '#1D4ED8',
    },
    {
        'name': 'Sheikh Zayed Branch',
        'address': 'Westown Hub, Sheikh Zayed, Giza',
        'phone': '+20 2 3850 9012',
        'workingDays': [0, 1, 2, 3, 4, 5],
        'rooms': [],
        'openTime': time(9, 30),
        'closeTime': time(18, 30),
        'isMain': False,
        'color': '#B45309',
    },
]

ROOMS = ['Room 1', 'Room 2', 'Room 3', 'Room 4', 'Consultation Room']

PROCEDURE_DATA = [
    # (name, category, duration_min, price)
    ('Routine Checkup', 'Routine Checkup', 30, Decimal('150.00')),
    ('Full Mouth Examination', 'Routine Checkup', 45, Decimal('200.00')),
    ('Dental X-Ray (Full)', 'Diagnostic', 20, Decimal('180.00')),
    ('Periapical X-Ray', 'Diagnostic', 10, Decimal('80.00')),
    ('Composite Filling', 'Restorative', 60, Decimal('350.00')),
    ('Amalgam Filling', 'Restorative', 45, Decimal('250.00')),
    ('Root Canal Treatment', 'Endodontic', 90, Decimal('1200.00')),
    ('Pulpotomy', 'Endodontic', 60, Decimal('600.00')),
    ('Teeth Cleaning (Scaling)', 'Preventive', 45, Decimal('300.00')),
    ('Fluoride Treatment', 'Preventive', 20, Decimal('150.00')),
    ('Tooth Extraction (Simple)', 'Surgical', 30, Decimal('400.00')),
    ('Surgical Extraction (Wisdom)', 'Surgical', 75, Decimal('900.00')),
    ('Dental Crown (Ceramic)', 'Prosthetic', 90, Decimal('2500.00')),
    ('Dental Bridge (3-unit)', 'Prosthetic', 120, Decimal('4500.00')),
    ('Dental Implant', 'Implant', 120, Decimal('5000.00')),
    ('Implant Crown', 'Implant', 60, Decimal('2000.00')),
    ('Teeth Whitening', 'Cosmetic', 60, Decimal('800.00')),
    ('Dental Veneer', 'Cosmetic', 90, Decimal('1500.00')),
    ('Orthodontic Consultation', 'Routine Checkup', 30, Decimal('200.00')),
    ('Gum Treatment (Deep Cleaning)', 'Preventive', 60, Decimal('600.00')),
]

INVENTORY_DATA = [
    # (name, category, unit, supplier, current_stock, min_stock)
    ('Disposable Gloves (Box)', 'Consumables', 'Box', 'MedSupply Co.', 40, 10),
    ('Face Masks (Box)', 'Consumables', 'Box', 'MedSupply Co.', 25, 8),
    ('Dental Floss Rolls', 'Consumables', 'Roll', 'DentalPro', 60, 15),
    ('Saliva Ejectors', 'Consumables', 'Pack', 'MedSupply Co.', 18, 10),
    ('Cotton Rolls', 'Consumables', 'Pack', 'DentalPro', 30, 10),
    ('Composite Resin (A1)', 'Materials', 'Syringe', 'DentMat Inc.', 12, 5),
    ('Composite Resin (A2)', 'Materials', 'Syringe', 'DentMat Inc.', 8, 5),
    ('Composite Resin (A3)', 'Materials', 'Syringe', 'DentMat Inc.', 3, 5),  #low stock
    ('Dental Cement (GIC)', 'Materials', 'Pack', 'DentMat Inc.', 6, 4),
    ('Bonding Agent', 'Materials', 'Bottle', 'DentMat Inc.', 7, 3),
    ('Lidocaine 2% Cartridges', 'Anesthetics', 'Box', 'PharmaDent', 20, 8),
    ('Articaine Cartridges', 'Anesthetics', 'Box', 'PharmaDent', 5, 5),  #low stock
    ('Epinephrine 1:100,000', 'Anesthetics', 'Box', 'PharmaDent', 15, 5),
    ('Dental Burs Set', 'Instruments', 'Set', 'InstrumentPro', 8, 3),
    ('Scalers (Ultrasonic Tips)', 'Instruments', 'Pack', 'InstrumentPro', 4, 3),
    ('Impression Material (Alginate)', 'Materials', 'Bag', 'DentMat Inc.', 9, 4),
    ('Disposable Syringes', 'Consumables', 'Pack', 'MedSupply Co.', 35, 10),
    ('Sterilization Pouches', 'Consumables', 'Box', 'MedSupply Co.', 12, 6),
    ('Hydrogen Peroxide 3%', 'Chemicals', 'Bottle', 'ChemDent', 10, 4),
    ('Cavity Detector Dye', 'Chemicals', 'Bottle', 'ChemDent', 2, 3),  #low stock
]

LAB_DATA = [
    # (name, phone, address, contact_person)
    ('Cairo Dental Lab', '+20-1001234567', '14 Tahrir Square, Cairo', 'Ahmed Fouad'),
    ('Smile Craft Lab', '+20-1009876543', '7 El Nasr Street, Heliopolis', 'Mona Khalil'),
    ('ProDent Lab', '+20-1005554433', '3 Westown Hub, Sheikh Zayed', 'Khaled Nasser'),
    ('Elite Dental Lab', '+20-1002223344', '22 Corniche El Nil, Giza', 'Sara Youssef'),
]

EXCEPTION_TYPES = [
    DoctorScheduleException.ExceptionTypeChoices.OFF,
    DoctorScheduleException.ExceptionTypeChoices.VACATION,
    DoctorScheduleException.ExceptionTypeChoices.CONFERENCE,
]


def _random_phone():
    '''Generate a phone number that passes validate_phone_number.'''
    return f'{random.randint(100, 999)}-{random.randint(1000000, 9999999)}'


def _random_past_date(years_back=5):
    return faker.date_between(start_date=f'-{years_back}y', end_date='today')


def _random_future_date(days_ahead=60):
    return faker.date_between(start_date='today', end_date=f'+{days_ahead}d')


def _random_time(hour_start=8, hour_end=18):
    hour = random.randint(hour_start, hour_end - 1)
    minute = random.choice([0, 15, 30, 45])
    from datetime import time
    return time(hour, minute)


# ── Seeding functions ──────────────────────────────────────────────────────────

# Seeding functions

def seed_branches():
    print('Seeding branches...')

    branches = [Branch(**branch_data) for branch_data in BRANCH_DATA]
    Branch.objects.bulk_create(branches)

    seeded_branches = list(Branch.objects.order_by('-isMain', 'name'))
    print(f'  Created {len(seeded_branches)} branches.')
    return seeded_branches


def seed_users(branches, num_users=10):
    '''Create one admin + a mix of dentists, receptionists, assistants.'''
    print('Seeding users...')

    roles_pool = (
        ['dentist'] * 4 +
        ['receptionist'] * 3 +
        ['assistant'] * 2 +
        ['accountant'] * 1
    )

    users = []

    #Always create one known admin for easy login
    admin = User.objects.create_user(
        email='admin@clinic.com',
        password='Admin123',
        name='Admin User',
        role='admin',
        branch=branches[0],
        is_staff=True,
    )
    users.append(admin)

    #Create two known dentists
    dentist1 = User.objects.create_user(
        email='dentist@clinic.com',
        password='Dentist123',
        name='Dentist User',
        role='dentist',
        branch=branches[0],
        is_staff=True,
    )
    
    dentist2 = User.objects.create_user(
        email='dentist2@clinic.com',
        password='Dentist123',
        name='Dentist User2',
        role='dentist',
        branch=branches[0],
        is_staff=True,
    )
    users.append(dentist1)
    users.append(dentist2)

    #Create one known receptionist
    receptionist = User.objects.create_user(
        email='receptionist@clinic.com',
        password='Receptionist123',
        name='Receptionist User',
        role='receptionist',
        branch=branches[0],
        is_staff=True,
    )
    users.append(receptionist)
    
    #Create one known assistant
    assistant = User.objects.create_user(
        email='assistant@clinic.com',
        password='Assistant123',
        name='Assistant User',
        role='assistant',
        branch=branches[0],
        is_staff=True,
    )
    users.append(assistant)

    #Create one known accountant
    accountant = User.objects.create_user(
        email='accountant@clinic.com',
        password='Accountant123',
        name='Accountant User',
        role='accountant',
        branch=branches[0],
        is_staff=True,
    )
    users.append(accountant)

    for i in range(num_users - 6):   #accounting for the 5 users created above
        role = roles_pool[i % len(roles_pool)]
        branch = random.choices(branches, weights=[70, 15, 15])[0]
        name = faker.name()
        email = faker.unique.email()
        user = User.objects.create_user(
            email=email,
            password='Test@1234',
            name=name,
            role=role,
            branch=branch,
            specialization='General Dentistry' if role == 'dentist' else None,
            is_staff=True,
        )
        users.append(user)

    print(f'  Created {len(users)} users.')
    return User.objects.filter(is_deleted=False)


def seed_procedures(branches):
    '''Create the standard procedure catalogue.'''
    print('Seeding procedures...')

    procedures = []
    for name, category, duration, price in PROCEDURE_DATA:
        procedures.append(Procedure(
            name=name,
            category=category,
            duration=duration,
            price=price,
            currency='USD',
            description=faker.text(max_nb_chars=150) if random.random() < 0.4 else None,
            branch=random.choices(branches, weights=[70, 15, 15])[0]
        ))

    Procedure.objects.bulk_create(procedures, ignore_conflicts=True)
    print(f'  Created {Procedure.objects.count()} procedures.')
    return list(Procedure.objects.all())


def seed_patients(doctors, num_patients=80):
    '''
    Create patients individually (not bulk_create) so that Patient.save()
    fires and auto-creates each patient's DentalChart.
    '''
    print('Seeding patients...')

    patients = []
    for _ in range(num_patients):
        country_code = random.choice(COUNTRY_CODES)
        has_allergies = random.random() < 0.3
        insurance = random.choice(INSURANCE_PROVIDERS)
        doctor = random.choice(doctors) if random.random() < 0.8 else None

        patient = Patient(
            doctor=doctor,
            branch=doctor.branch if doctor else None,
            name=faker.name(),
            age=random.randint(5, 85),
            gender=random.choice(['Male', 'Female']),
            countryCode=country_code,
            phone=_random_phone(),
            email=faker.email() if random.random() < 0.6 else None,
            nationalId=faker.bothify('#########') if random.random() < 0.5 else None,
            address=faker.address()[:200] if random.random() < 0.5 else None,
            bloodType=random.choice(BLOOD_TYPES) if random.random() < 0.5 else None,
            allergies=random.sample(COMMON_ALLERGIES, k=random.randint(1, 3)) if has_allergies else [],
            insurance=insurance,
            insuranceId=faker.bothify('INS-####-????').upper() if insurance else None,
            status=random.choices(['active', 'inactive'], weights=[85, 15])[0],
            notes=faker.text(max_nb_chars=150) if random.random() < 0.2 else None,
        )
        #save() triggers DentalChart creation + phone normalization
        patient.save()
        patients.append(patient)

    print(f'  Created {len(patients)} patients (+ dental charts auto-created).')
    return list(Patient.objects.all())


def seed_visits(patients, doctors, num_visits=150):
    '''
    Create visit records. Uses .save() individually so that patient.lastVisit
    is updated correctly per the Visit.save() override.
    '''
    print('Seeding visits...')

    procedure_names = [p[0] for p in PROCEDURE_DATA]
    count = 0

    for _ in range(num_visits):
        patient = random.choice(patients)
        doctor = random.choice([d for d in doctors if d.role in ('dentist', 'admin')] or doctors)
        visit_date = _random_past_date(years_back=3)
        procedures_done = random.sample(procedure_names, k=random.randint(1, 3))
        cost = Decimal(str(round(random.uniform(150, 3000), 2)))
        paid = cost if random.random() < 0.75 else Decimal(str(round(float(cost) * random.uniform(0.3, 0.9), 2)))

        visit = Visit(
            doctor=doctor,
            patient=patient,
            date=visit_date,
            type=procedures_done[0],
            procedures=procedures_done,
            cost=cost,
            paid=paid,
            currency='USD',
            xray=random.random() < 0.2,
            notes=faker.text(max_nb_chars=100) if random.random() < 0.25 else None,
        )
        visit.save()
        count += 1

    print(f'  Created {count} visits.')
    return list(Visit.objects.all())


def seed_appointments(patients, doctors, procedures, num_appointments=120):
    '''
    Create appointments. Uses .save() so patient.nextAppointment is updated.
    Appointments are spread across past and future dates.
    '''
    print('Seeding appointments...')

    count = 0
    for _ in range(num_appointments):
        patient = random.choice(patients)
        doctor = random.choice([d for d in doctors if d.role in ('dentist', 'admin')] or doctors)
        branch = doctor.branch
        procedure = random.choice(procedures)

        #Mix of past (completed/cancelled) and upcoming (pending/confirmed)
        is_future = random.random() < 0.20
        appt_date = _random_future_date(35) if is_future else _random_past_date(2)

        #Future appointments should be pending or confirmed
        if is_future:
            status = random.choice(['pending', 'confirmed'])
        else:
            status = random.choices(['completed', 'cancelled', 'confirmed'], weights=[65, 20, 15])[0]

        start_time = _random_time()
        duration = procedure.duration or 30
        start_dt = datetime.combine(appt_date, start_time)
        end_dt = start_dt + timedelta(minutes=duration)
        end_time = end_dt.time()

        appt = Appointment(
            doctor=doctor,
            branch=branch,
            patient=patient,
            procedure=procedure,
            date=appt_date,
            startTime=start_time,
            endTime=end_time,
            type=procedure.name,
            room=random.choice(ROOMS),
            status=status,
            notes=faker.text(max_nb_chars=100) if random.random() < 0.2 else None,
        )
        appt.save()
        count += 1

    print(f'  Created {count} appointments.')
    return list(Appointment.objects.all())


def seed_treatment_plans(patients, doctors, procedures, num_plans=60):
    print('Seeding treatment plans...')

    statuses = ['active', 'completed', 'cancelled']
    status_weights = [50, 30, 20]
    item_statuses = ['pending', 'in_progress', 'completed']
    item_status_weights = [40, 35, 25]
    installment_options = [1, 3, 6, 12]
    installments_weights = [40, 30, 20, 10]
    count = 0

    for _ in range(num_plans):
        patient = random.choice(patients)
        doctor = random.choice([d for d in doctors if d.role in ('dentist', 'admin')] or doctors)
        plan_procedures = random.sample(procedures, k=random.randint(1, 4))

        #Build items data first to calculate totalCost
        items_data = [
            {
                'procedure': proc,
                'session': i+1,
                'toothNumber': random.choice(FDI_TEETH_LIST) if random.random() < 0.7 else None,
                'price': proc.price + Decimal(str(round(random.uniform(-50, 100), 2))),
                'status': random.choices(item_statuses, weights=item_status_weights)[0],
                'notes': faker.text(max_nb_chars=150) if random.random() < 0.3 else None,
            }
            for i,proc in enumerate(plan_procedures)
        ]

        num_installments = random.choices(installment_options, weights=installments_weights)[0]
        paidAmount = sum(item['price'] for item in items_data) if num_installments==1 else None

        plan = TreatmentPlan(
            doctor=doctor,
            patient=patient,
            currency='USD',
            paidAmount=paidAmount,
            totalCost=sum(item['price'] for item in items_data),
            sessions=sum(item['session'] for item in items_data),
            status=random.choices(statuses, weights=status_weights)[0],
            title=faker.text(max_nb_chars=70) if random.random() < 0.85 else None,
            installmentMonths=num_installments
        )
        plan.save()

        TreatmentPlanItem.objects.bulk_create([
            TreatmentPlanItem(
                treatmentPlan=plan,
                procedure=item['procedure'],
                toothNumber=item['toothNumber'],
                price=item['price'],
                session=item['session'],
                status=item['status'],
                notes=item['notes']
            )
            for item in items_data
        ])
        count += 1

    print(f'  Created {count} treatment plans.')
    return list(TreatmentPlan.objects.all())


def seed_patient_recalls(patients, branches, num_recalls=60):
    '''
    Create patient recalls individually so that PatientRecall.save() fires
    and auto-assigns phone from patient if not provided.
    '''
    print('Seeding patient recalls...')

    recall_types = [c[0] for c in PatientRecall.RecallTypeChoices.choices]
    safe_statuses = [
        PatientRecall.RecallStatusChoices.PENDING,
        PatientRecall.RecallStatusChoices.NO_ANSWER,
        PatientRecall.RecallStatusChoices.CONFIRMED,
        PatientRecall.RecallStatusChoices.DECLINED,
    ]   #skipping CONTACTED to avoid auto-setting contactedAt during seeding
    count = 0

    for _ in range(num_recalls):
        patient = random.choice(patients)
        branch = patient.branch or random.choices(branches, weights=[70, 15, 15])[0]

        recall = PatientRecall(
            patient=patient,
            branch=branch,
            type=random.choice(recall_types),
            status=random.choice(safe_statuses),
            dueDate=_random_future_date(days_ahead=180),
            notes=faker.text(max_nb_chars=150) if random.random() < 0.25 else None,
            #phone intentionally omitted -- save() pulls it from patient
        )
        recall.save()
        count += 1

    print(f'  Created {count} patient recalls.')
    return list(PatientRecall.all_objects.all())


def seed_labs(branches):
    '''Create labs, each optionally tied to a branch.'''
    print('Seeding labs...')

    labs = []
    for name, phone, address, contact_person in LAB_DATA:
        labs.append(Lab(
            name=name,
            phone=phone,
            address=address,
            contactPerson=contact_person,
            notes=faker.text(max_nb_chars=150) if random.random() < 0.3 else None,
            branch=random.choices(branches + [None], weights=[40, 20, 20, 20])[0]
        ))

    Lab.all_objects.bulk_create(labs)
    print(f'  Created {Lab.all_objects.count()} labs.')
    return list(Lab.all_objects.all())


def seed_lab_orders(labs, patients, procedures, branches, num_orders=40):
    '''
    Create lab orders individually so that LabOrder.save() fires.
    Avoids status=RECEIVED/DELIVERED to sidestep the .date bug in save().
    '''
    print('Seeding lab orders...')

    safe_statuses = [
        LabOrder.OrderStatusChoices.SENT,
        LabOrder.OrderStatusChoices.IN_PRODUCTION,
    ]
    count = 0

    for _ in range(num_orders):
        lab = random.choice(labs)
        patient = random.choice(patients)
        procedure = random.choice(procedures)
        branch = random.choices(branches + [None], weights=[60, 15, 15, 10])[0]
        sent_date = _random_past_date(years_back=1)
        due_date = sent_date + timedelta(days=random.randint(3, 21))

        order = LabOrder(
            lab=lab,
            patient=patient,
            procedure=procedure,
            branch=branch,
            toothNumber=random.choice(FDI_TEETH_LIST),
            instructions=faker.text(max_nb_chars=200) if random.random() < 0.5 else None,
            sentDate=sent_date,
            dueDate=due_date,
            status=random.choice(safe_statuses),
            cost=Decimal(str(round(random.uniform(100, 2000), 2))),
            currency='USD',
        )
        order.save()
        count += 1

    print(f'  Created {count} lab orders.')
    return list(LabOrder.all_objects.all())


def seed_inventory(branches):
    '''
    Create inventory items. lastOrdered is set directly here
    to work around the Inventory.save() bug (updatedAt.date not called).
    '''
    print('Seeding inventory...')

    items = []
    for name, category, unit, supplier, current_stock, min_stock in INVENTORY_DATA:
        items.append(Inventory(
            name=name,
            category=category,
            unit=unit,
            supplier=supplier,
            currentStock=current_stock,
            minStock=min_stock,
            lastOrdered=_random_past_date(years_back=1),  #set directly, bypassing the save() bug
            branch=random.choices(branches, weights=[70, 15, 15])[0]
        ))

    Inventory.objects.bulk_create(items)
    print(f'  Created {Inventory.objects.count()} inventory items.')
    return list(Inventory.objects.all())


def seed_waiting_room(appointments, num_entries=10):
    '''
    Create waiting room entries for past appointments.
    '''
    print('Seeding waiting room...')

    #Only attach to past completed/confirmed appointments
    eligible = [a for a in appointments if a.status in ('completed', 'confirmed') and a.date < date.today()]
    if not eligible:
        print('  No eligible appointments for waiting room. Skipping.')
        return []

    safe_statuses = [
        WaitingRoom.StatusChoices.WAITING,
        WaitingRoom.StatusChoices.IN_CHAIR,
    ]
    sample = random.sample(eligible, k=min(num_entries, len(eligible)))
    count = 0

    for appt in sample:
        #WaitingRoom.save() auto-sets arrivedAt, so no need to pass it
        entry = WaitingRoom(
            appointment=appt,
            branch=appt.branch,
            room=random.choice(ROOMS) if random.random() < 0.7 else None,
            status=random.choice(safe_statuses),
        )
        entry.save()
        count += 1

    print(f'  Created {count} waiting room entries.')
    return list(WaitingRoom.all_objects.all())


def seed_doctor_schedules(doctors):
    '''Create one schedule per doctor. Skips doctors that already have one.'''
    print('Seeding doctor schedules...')

    days_pool = [
        [0, 1, 2, 3, 4],
        [0, 1, 2, 3, 4, 5],
        [0, 2, 4],
        [1, 3, 5],
    ]
    count = 0

    for doctor in doctors:
        #OneToOneField -- skip if already exists
        if DoctorSchedule.all_objects.filter(doctor=doctor).exists():
            continue

        has_break = random.random() < 0.6
        break_start = time(13, 0) if has_break else None
        break_end = time(14, 0) if has_break else None

        DoctorSchedule.objects.create(
            doctor=doctor,
            workingDays=random.choice(days_pool),
            startTime=time(random.choice([8, 9, 10]), 0),
            endTime=time(random.choice([17, 18, 19]), 0),
            breakStart=break_start,
            breakEnd=break_end,
        )
        count += 1

    print(f'  Created {count} doctor schedules.')
    return list(DoctorSchedule.all_objects.all())


def seed_schedule_exceptions(doctors, num_exceptions=30):
    '''
    Create schedule exceptions for doctors that have an existing DoctorSchedule.
    Uses bulk_create since there's no meaningful save() override on the model.
    '''
    print('Seeding schedule exceptions...')

    #Collect all schedules across all non-deleted doctors
    schedules = []
    for doctor in doctors:
        #OneToOneField reverse accessor, skip doctors with no schedule yet
        try:
            schedules.append(doctor.doctor_schedule)
        except DoctorSchedule.DoesNotExist:
            continue

    if not schedules:
        print('  No doctor schedules found. Skipping.')
        return []

    exceptions = []
    for _ in range(num_exceptions):
        schedule = random.choice(schedules)
        exceptions.append(
            DoctorScheduleException(
                schedule=schedule,
                date=_random_future_date(days_ahead=90),
                type=random.choice(EXCEPTION_TYPES),
                note=faker.text(max_nb_chars=100) if random.random() < 0.4 else None
            ))

    DoctorScheduleException.all_objects.bulk_create(exceptions, ignore_conflicts=True)
    count = DoctorScheduleException.all_objects.count()
    print(f'  Created {count} schedule exceptions.')
    return list(DoctorScheduleException.all_objects.all())


def seed_sterilization_logs(branches, users, num_logs=50):
    '''
    Create sterilization logs. date/time defaults fire via lambda on instantiation,
    but we override them here with varied past dates for realistic seed data.
    '''
    print('Seeding sterilization logs...')

    cycle_types = [c[0] for c in SterilizationLog.CycleTypeChoices.choices]
    instrument_sets = [c[0] for c in SterilizationLog.InstrumentSetsChoices.choices]
    results = [c[0] for c in SterilizationLog.SterilizationResultChoices.choices]
    result_weights = [85, 15]   #mostly passing cycles

    logs = []
    for _ in range(num_logs):
        branch = random.choices(branches, weights=[70, 15, 15])[0]
        #Pick a random operator from staff at any branch
        operator = random.choice(users)
        log_date = _random_past_date(years_back=1)
        shelf_life = random.choice([30, 60, 90, 180, None])

        logs.append(SterilizationLog(
            date=log_date,
            time=_random_time(hour_start=7, hour_end=18),
            operator=operator.name,
            cycleType=random.choice(cycle_types),
            instrumentSets=random.sample(instrument_sets, k=random.randint(1, 4)),
            result=random.choices(results, weights=result_weights)[0],
            sealedAt=log_date + timedelta(days=random.randint(0, 2)) if random.random() < 0.7 else None,
            shelfLifeDays=shelf_life,
            notes=faker.text(max_nb_chars=150) if random.random() < 0.25 else None,
            branch=branch,
        ))

    SterilizationLog.all_objects.bulk_create(logs)
    count = SterilizationLog.all_objects.count()
    print(f'  Created {count} sterilization logs.')
    return list(SterilizationLog.all_objects.all())



# ── Main ───────────────────────────────────────────────────────────────────────

@transaction.atomic
def run_seed(num_users=10, num_patients=80, num_visits=150,
             num_appointments=120, num_plans=60, num_recalls=60, 
             num_lab_orders=40, num_waiting_room=10, num_schedule_exceptions=30, 
             num_sterilization_logs=50):

    print('\n', '=' * 50)
    print('  Starting data seeding...')
    print('=' * 50, '\n')

    #Clear existing data in reverse dependency order
    print('Clearing existing data...')
    Patient.all_objects.all().delete()   # cascades to DentalChart, XRay
    Visit.all_objects.all().delete()
    Appointment.all_objects.all().delete()
    TreatmentPlan.all_objects.all().delete()
    PatientRecall.all_objects.all().delete()
    Procedure.objects.all().delete()
    Inventory.objects.all().delete()
    DoctorSchedule.all_objects.all().delete()  # cascades to DoctorScheduleException
    LabOrder.all_objects.all().delete()
    Lab.all_objects.all().delete()
    SterilizationLog.objects.all().delete()
    WaitingRoom.all_objects.all().delete()
    Branch.objects.all().delete()
    User.all_objects.filter(is_superuser=False).delete()
    print('  Done.\n')

    #Seed in dependency order
    branches = seed_branches()
    users = seed_users(branches, num_users)
    doctors = list(users.filter(role__in=['dentist', 'admin']))
    seed_doctor_schedules(doctors)
    seed_schedule_exceptions(doctors, num_schedule_exceptions)
    procedures = seed_procedures(branches)
    patients = seed_patients(doctors, num_patients)
    seed_visits(patients, doctors, num_visits)
    appointments = seed_appointments(patients, doctors, procedures, num_appointments)
    seed_treatment_plans(patients, doctors, procedures, num_plans)
    seed_patient_recalls(patients, branches, num_recalls)
    seed_inventory(branches)
    labs = seed_labs(branches)
    seed_lab_orders(labs, patients, procedures, branches, num_lab_orders)
    seed_waiting_room(appointments, num_waiting_room)
    sterilization_logs = seed_sterilization_logs(branches, users, num_sterilization_logs)

    #Summary
    print('\n', '=' * 50)
    print('  Seeding completed!')
    print('=' * 50)
    print(f'  Users:               {User.objects.count()}')
    print(f'  Branches:            {Branch.objects.count()}')
    print(f'  Doctor Schedules:    {DoctorSchedule.objects.count()}')
    print(f'  Schedule Exceptions: {DoctorScheduleException.objects.count()}')
    print(f'  Patients:            {Patient.objects.count()}')
    print(f'  Dental Charts:       {Patient.objects.count()} (auto-created)')
    print(f'  Visits:              {Visit.objects.count()}')
    print(f'  Appointments:        {Appointment.objects.count()}')
    print(f'  Treatment Plans:     {TreatmentPlan.objects.count()}')
    print(f'  Patient Recalls:     {PatientRecall.objects.count()}')
    print(f'  Waiting Room:        {WaitingRoom.objects.count()}')
    print(f'  Procedures:          {Procedure.objects.count()}')
    print(f'  Labs:                {Lab.objects.count()}')
    print(f'  Lab Orders:          {LabOrder.objects.count()}')
    print(f'  Inventory Items:     {Inventory.objects.count()}')
    print(f'  Low Stock Items:     {Inventory.objects.filter(currentStock__lt=F("minStock")).count()}')
    print(f'  Sterilization Logs:  {SterilizationLog.objects.count()}')
    print('=' * 50, '\n')


if __name__ == '__main__':
    while True:
        try:
            run_seed(num_users=25, 
                     num_patients=100, 
                     num_visits=200,
                     num_appointments=120,
                     num_plans=60,
                     num_recalls=60,
                     num_lab_orders=40,
                     num_waiting_room=10,
                     num_schedule_exceptions=30, 
                     num_sterilization_logs=50
                    )
                
            break   #break upon successful seeding

        except Exception as exc:
            import traceback
            print(f'\nSeeding error: {exc}')
            traceback.print_exc()
            print('\nRetrying...\n', '=' * 50)
