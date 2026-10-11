import os
import sys
import random
import django
from faker import Faker
from pathlib import Path
from decimal import Decimal
from django.utils import timezone
from itertools import zip_longest
from datetime import datetime, date, time, timedelta

#Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

#Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DentalTech.settings.dev')
django.setup()


from django.db.models import F
from django.http import Http404
from django.db import transaction
from patients.validators import FDI_PERMANENT
from users.models import User, DoctorSchedule, DoctorScheduleException
from clinic.models import Branch, Procedure, Inventory, Lab, LabOrder, WaitingRoom, SterilizationLog
from finances.models import (ClinicalTaxConfig, InsuranceProvider, Bill, Transaction, InstallmentPlan, 
                             Installment, Invoice, InvoiceItem)
from patients.models import (Patient, Visit, Appointment, TreatmentPlan, TreatmentPlanItem, PatientRecall, 
                             PatientCoverage, PerioExam, InboundReferral, OutboundReferral)


#Instantiate faker
faker = Faker()


# ── Helpers ────────────────────────────────────────────────────────────────────

COUNTRY_CODES = ['+20', '+966', '+971', '+974', '+965', '+973', '+968', '+1']

BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

COMMON_ALLERGIES = [
    'Penicillin', 'Amoxicillin', 'Latex', 'Aspirin', 'Ibuprofen',
    'Codeine', 'Sulfa drugs', 'Lidocaine', 'Epinephrine', 'Nickel'
]

INSURANCE_PROVIDERS_DATA = [
    {
        'name': 'MetLife Egypt',
        'fullName': 'MetLife Egypt Insurance',
        'region': 'Egypt',
        'tier': 'corporate',
        'contact': '19556',
        'coveragePercent': 80,
        'annualMax': Decimal('5000.00'),
        'deductible': Decimal('300.00'),
        'currency': 'EGP',
        'responseDays': 5,
        'color': '#1D4ED8',
        'notes': 'Corporate group policies only. Pre-auth required for crowns, implants, endo.',
    },
    {
        'name': 'AXA Egypt',
        'fullName': 'AXA Egypt Insurance',
        'region': 'Egypt',
        'tier': 'corporate',
        'contact': '19111',
        'coveragePercent': 75,
        'annualMax': Decimal('4000.00'),
        'deductible': Decimal('200.00'),
        'currency': 'EGP',
        'responseDays': 7,
        'color': '#DC2626',
        'notes': None,
    },
    {
        'name': 'GAIH',
        'fullName': 'General Authority for Insurance and Health',
        'region': 'Egypt',
        'tier': 'government',
        'contact': '16770',
        'coveragePercent': 90,
        'annualMax': Decimal('3000.00'),
        'deductible': Decimal('0.00'),
        'currency': 'EGP',
        'responseDays': 10,
        'color': '#15803D',
        'notes': 'Government employees only.',
    },
    {
        'name': 'Allianz Egypt',
        'fullName': 'Allianz Egypt Insurance',
        'region': 'Egypt',
        'tier': 'universal',
        'contact': '19700',
        'coveragePercent': 70,
        'annualMax': Decimal('2000.00'),
        'deductible': Decimal('500.00'),
        'currency': 'EGP',
        'responseDays': 5,
        'color': '#1E40AF',
        'notes': None,
    },
    {
        'name': 'Takaful & Karama',
        'fullName': 'Takaful and Karama Insurance',
        'region': 'Egypt',
        'tier': 'universal',
        'contact': '16060',
        'coveragePercent': 60,
        'annualMax': Decimal('1000.00'),
        'deductible': Decimal('100.00'),
        'currency': 'EGP',
        'responseDays': 14,
        'color': '#7C3AED',
        'notes': None,
    },
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

    seeded_branches = list(Branch.objects.order_by('name'))
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
        name='Dr. Admin',
        role='admin',
        branch=branches[0],
        is_staff=True,
    )
    admin.branches.set(branches)
    users.append(admin)

    #Create two known dentists
    dentist1 = User.objects.create_user(
        email='dentist@clinic.com',
        password='Dentist123',
        name='Dr. Ehab',
        role='dentist',
        branch=branches[0],
        is_staff=True,
    )
    
    dentist2 = User.objects.create_user(
        email='dentist2@clinic.com',
        password='Dentist123',
        name='Dr. Abdallah',
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

    for i in range(num_users - 6):   #accounting for the 6 users created above
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
            currency='EGP',
            description=faker.text(max_nb_chars=150) if random.random() < 0.4 else None,
            branch=random.choices(branches, weights=[70, 15, 15])[0]
        ))

    Procedure.objects.bulk_create(procedures, ignore_conflicts=True)
    print(f'  Created {Procedure.objects.count()} procedures.')
    return list(Procedure.objects.all())


def seed_insurance_providers(branches):
    print('Seeding insurance providers...')

    providers = []
    for data in INSURANCE_PROVIDERS_DATA:
        branch = random.choices(branches, weights=[70, 15, 15])[0]
        providers.append(
            InsuranceProvider(**data, branch=branch)
        )
    InsuranceProvider.objects.bulk_create(providers, ignore_conflicts=True)
    result = list(InsuranceProvider.objects.all())
    print(f'  Created {len(result)} insurance providers.')
    return result


def seed_patients(doctors, insurance_providers, num_patients=80):
    print('Seeding patients...')

    patients = []
    for _ in range(num_patients):
        country_code = random.choice(COUNTRY_CODES)
        has_allergies = random.random() < 0.3
        doctor = random.choice(doctors) if random.random() < 0.8 else None        
        provider = random.choice(insurance_providers) if random.random() < 0.5 else None

        patient = Patient(
            doctor=doctor,
            branch=doctor.branch if doctor else None,
            name=faker.name(),
            age=random.randint(5, 85),
            gender=random.choice(['male', 'female']),
            countryCode=country_code,
            phone=_random_phone(),
            email=faker.email() if random.random() < 0.6 else None,
            nationalId=faker.bothify('#########') if random.random() < 0.5 else None,
            address=faker.address()[:200] if random.random() < 0.5 else None,
            bloodType=random.choice(BLOOD_TYPES) if random.random() < 0.5 else None,
            allergies=random.sample(COMMON_ALLERGIES, k=random.randint(1, 3)) if has_allergies else [],
            # insurance=insurance,
            # insuranceId=faker.bothify('INS-####-????').upper() if insurance else None,
            status=random.choices(['active', 'inactive'], weights=[90, 10])[0],
            notes=faker.text(max_nb_chars=150) if random.random() < 0.2 else None,
        )
        #save() triggers DentalChart creation + insurance coverage creation
        patient.save(provider=provider)

        #if has insurance, populate coverage details
        if provider:
            coverage = patient.patient_insurance
            coverage.memberId = faker.bothify(f'{provider.name[:2].upper()}-EG-####-#####').upper()
            coverage.annualMax = provider.annualMax
            coverage.deductibleMet = random.random() < 0.4
            coverage.effectiveFrom = date(timezone.localdate(timezone.now()).year, 1, 1)
            coverage.effectiveTo = date(timezone.localdate(timezone.now()).year, 12, 31)
            coverage.eligibilityChecked = _random_past_date(years_back=1)
            coverage.eligibilityStatus = random.choices(
                ['active', 'expiring', 'expired', 'limit_reached', 'none'],
                weights=[60, 10, 15, 10, 5]
            )[0]
            coverage.currency = 'EGP'
            coverage.save()


        patients.append(patient)

    print(f'  Created {len(patients)} patients (+ dental charts + coverages auto-created).')
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
        visit_type = random.choice(Visit.VisitTypeChoices.values)
        procedures_done = random.sample(procedure_names, k=random.randint(1, 3))
        cost = Decimal(str(round(random.uniform(150, 3000), 2)))
        paid = cost if random.random() < 0.75 else Decimal(str(round(float(cost) * random.uniform(0.3, 0.9), 2)))

        visit = Visit(
            doctor=doctor,
            patient=patient,
            date=visit_date,
            type=visit_type,
            procedures=procedures_done,
            cost=cost,
            paid=paid,
            currency='EGP',
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
        appt_type = random.choice(Visit.VisitTypeChoices.values)
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
            type=appt_type,
            room=random.choice(ROOMS),
            status=status,
            notes=faker.text(max_nb_chars=100) if random.random() < 0.2 else None,
        )
        appt.save()
        count += 1

    print(f'  Created {count} appointments.')
    return list(Appointment.objects.all())


def seed_treatment_plans(patients, doctors, procedures, num_treatment_plans=60):
    print('Seeding treatment plans...')

    statuses = ['active', 'completed', 'cancelled']
    status_weights = [50, 30, 20]
    item_statuses = ['pending', 'in_progress', 'completed']
    item_status_weights = [40, 35, 25]
    count = 0

    for _ in range(num_treatment_plans):
        patient = random.choice(patients)
        doctor = random.choice([d for d in doctors if d.role in ('dentist', 'admin')] or doctors)
        plan_procedures = random.sample(procedures, k=random.randint(1, 4))

        #Build items data first to calculate totalCost
        treatment_items = [
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

        plan = TreatmentPlan(
            doctor=doctor,
            patient=patient,
            currency='EGP',
            totalCost=sum(item['price'] for item in treatment_items),
            sessions=sum(item['session'] for item in treatment_items),
            status=random.choices(statuses, weights=status_weights)[0],
            title=faker.text(max_nb_chars=70) if random.random() < 0.85 else None,
        )
        plan.save()

        TreatmentPlanItem.objects.bulk_create([
            TreatmentPlanItem(
                treatmentPlan=plan,
                procedure=item['procedure'],
                procedureName=item['procedure'].name,
                toothNumber=item['toothNumber'],
                price=item['price'],
                session=item['session'],
                status=item['status'],
                notes=item['notes']
            )
            for item in treatment_items
        ])
        count += 1

    print(f'  Created {count} treatment plans.')
    return list(TreatmentPlan.objects.all())

def seed_perio_exams(patients, doctors, num_exams_per_patient=5):
    print('Seeding periodontal exams...')

    site_names = ['DB', 'B', 'MB', 'DP', 'P', 'MP']

    exams = []
    for patient in patients:
        for _ in range(num_exams_per_patient):
            teeth = {}
            for tooth_number in random.sample(
                list(FDI_PERMANENT), k=random.randint(4, min(12, len(FDI_PERMANENT)))
            ):
                sites = {}
                for site_name in random.sample(site_names, k=random.randint(3, len(site_names))):
                    probing_depth = random.randint(1, 8) if random.random() < 0.85 else None
                    sites[site_name] = {
                        'probingDepth': probing_depth,
                        'recession': random.randint(0, 4) if random.random() < 0.6 else None,
                        'bleeding': bool(random.getrandbits(1)) if probing_depth is not None else False,
                        'plaque': bool(random.getrandbits(1)),
                        'suppuration': random.random() < 0.05,
                        'calculus': random.random() < 0.2,
                    }

                teeth[str(tooth_number)] = {
                    'mobility': random.choice([None, 0, 0, 1, 2]),
                    'furcation': random.choice([None, 0, 0, 1, 2]),
                    'sites': sites,
                }

            doctor = patient.doctor if patient.doctor and random.random() < 0.8 else random.choice(doctors)
            sites_probed, mean_depth, bleeding_percent = PerioExam.compute_perio_summary(teeth)

            exams.append(PerioExam.objects.create(
                patient=patient,
                examinedBy=doctor,
                examinedByName=doctor.name,
                examinedAt=faker.date_between(start_date='-2y', end_date='today'),
                teeth=teeth,
                sitesProbed=sites_probed,
                meanProbingDepth=mean_depth,
                bleedingPercent=bleeding_percent,
                notes=faker.text(max_nb_chars=150) if random.random() < 0.25 else None,
            ))

        print(f'  Created {len(exams)} periodontal exams.')
        return exams


def seed_patient_recalls(patients, branches, num_recalls=60):
    '''
    Create patient recalls individually so that PatientRecall.save() fires
    and auto-assigns phone from patient if not provided.
    '''
    print('Seeding patient recalls...')

    count = 0
    for _ in range(num_recalls):
        patient = random.choice(patients)
        branch = patient.branch or random.choices(branches, weights=[70, 15, 15])[0]

        recall = PatientRecall(
            patient=patient,
            branch=branch,
            type=random.choice(PatientRecall.RecallTypeChoices.values),
            status=random.choice(['pending', 'no_answer', 'confirmed', 'declined']),
            dueDate=_random_future_date(days_ahead=180),
            notes=faker.text(max_nb_chars=150) if random.random() < 0.25 else None,
            #phone intentionally omitted -- save() pulls it from patient
        )
        recall.save()
        count += 1

    print(f'  Created {count} patient recalls.')
    return list(PatientRecall.all_objects.all())


def seed_referrals(branches, doctors, patients, num_inbound=30, num_outbound=30):
    print('Seeding referrals...')

    # A user can be a referral source only once per branch.
    user_branch_pairs = [(doctor, branch) for doctor in doctors for branch in branches]
    user_referrals = random.sample(
        user_branch_pairs, min(num_inbound // 2, len(user_branch_pairs))
    )

    inbound = []
    for doctor, branch in user_referrals:
        inbound.append(InboundReferral.objects.create(
            referredByUser=doctor,
            branch=branch,
            speciality=random.choice(
                [choice.value for choice in InboundReferral.SpecialityChoices]
            ),
            notes=faker.text(max_nb_chars=120) if random.random() < 0.3 else None,
        ))

    # The remaining inbound referrals represent external clinics.
    for _ in range(num_inbound - len(user_referrals)):
        inbound.append(InboundReferral.objects.create(
            branch=random.choice(branches) if branches else None,
            name=faker.name(),
            clinic=faker.company(),
            speciality=random.choice(
                [choice.value for choice in InboundReferral.SpecialityChoices]
            ),
            phone=faker.phone_number(),
            email=faker.email() if random.random() < 0.6 else None,
            notes=faker.text(max_nb_chars=120) if random.random() < 0.3 else None,
        ))

    outbound = []
    if patients and (doctors or inbound):
        for _ in range(num_outbound):
            use_user = bool(doctors) and (not inbound or random.random() < 0.5)
            target_user = random.choice(doctors) if use_user else None
            target_entity = random.choice(inbound) if not use_user and inbound else None

            outbound.append(OutboundReferral.objects.create(
                patient=random.choice(patients),
                branch=random.choice(branches) if branches else None,
                referredToUser=target_user,
                referredToEntity=target_entity,
                status=random.choice(
                    [choice.value for choice in OutboundReferral.ReferralStatusChoices]
                ),
                outcome=faker.text(max_nb_chars=120) if random.random() < 0.3 else None,
                notes=faker.text(max_nb_chars=120) if random.random() < 0.3 else None,
            ))

    print(f'  Created {len(inbound)} inbound and {len(outbound)} outbound referrals.')
    return inbound, outbound


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
    print('Seeding lab orders...')

    statuses = [
        LabOrder.OrderStatusChoices.SENT,
        LabOrder.OrderStatusChoices.IN_PRODUCTION,
        LabOrder.OrderStatusChoices.RECEIVED,
        LabOrder.OrderStatusChoices.DELIVERED,
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
            status=random.choice(statuses),
            cost=Decimal(str(round(random.uniform(100, 2000), 2))),
            currency='EGP',
        )
        order.save()
        count += 1

    print(f'  Created {count} lab orders.')
    return list(LabOrder.all_objects.all())


def seed_inventory(branches):
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
            lastOrdered=_random_past_date(years_back=1),
            branch=random.choices(branches, weights=[70, 15, 15])[0]
        ))

    Inventory.objects.bulk_create(items)
    print(f'  Created {Inventory.objects.count()} inventory items.')
    return list(Inventory.objects.all())


def seed_clinical_tax_configs(branches):
    print('Seeding clinical tax configs...')

    created = 0
    for branch in branches:
        _, was_created = ClinicalTaxConfig.all_objects.get_or_create(
            branch=branch,
            defaults={
                'clinicName': f'DentalTech {branch.name}',
                'taxId': faker.bothify('TAX-########') if random.random() < 0.7 else None,
                'activityCode': faker.bothify('ACT-####'),
                'commercialReg': faker.bothify('CR-########'),
                'address': branch.address,
                'phone': _random_phone(),
            }
        )
        if was_created:
            created += 1

    print(f'  Created {created} clinical tax configs.')
    return list(ClinicalTaxConfig.all_objects.all())


def seed_bills(visits, treatments, installment_plans, num_bills=70):
    print('Seeding bills...')

    #Only use visits whose patient has a branch, since Bill.branch is required on save()
    eligible_visits = [
        visit for visit in visits if visit.patient_id and visit.patient.branch_id
    ]

    if not eligible_visits:
        print('  No eligible visits for bills. Skipping.')
        return []

    visits_by_patient = {}
    for visit in eligible_visits:
        visits_by_patient.setdefault(visit.patient_id, []).append(visit)

    #prepare lookup dict for installment plans
    planned_treatment_ids = {plan.treatment_id for plan in installment_plans}
    direct_treatments_by_patient = {}

    #assign plans
    for treatment in treatments:
        if treatment.id not in planned_treatment_ids:
            direct_treatments_by_patient.setdefault(
                treatment.patient_id, []
            ).append(treatment)

    #helper function
    def attach_visits(bill, patient_id):
        patient_visits = visits_by_patient.get(patient_id, [])
        if patient_visits:
            bill.visits.set(
                random.sample(
                    patient_visits,
                    k=random.randint(1, min(3, len(patient_visits))),
                )
            )

    count = 0
    bills = []

    # Exactly one active bill for every installment plan.
    for plan in installment_plans:
        treatment = plan.treatment
        patient = treatment.patient
        total = plan.totalAmount or treatment.totalCost

        bill = Bill.objects.create(
            patient=patient,
            treatment=treatment,
            installmentPlan=plan,
            branch=plan.branch or patient.branch,
            description=f'Installment plan — {treatment.title or "Treatment"}',
            subtotal=total,
            discount=Decimal('0.00'),
            totalAmount=total,
            totalPaid=Decimal('0.00'),
            currency=plan.currency or treatment.currency or 'EGP',
            createdBy=getattr(treatment.doctor, 'name', None),
        )
        attach_visits(bill, patient.id)
        bills.append(bill)

    # Fill the remainder with regular visit or direct-treatment bills.
    for _ in range(num_bills - len(bills)):
        base_visit = random.choice(eligible_visits)
        patient = base_visit.patient
        available_treatments = direct_treatments_by_patient.get(patient.id, [])

        treatment = (
            random.choice(available_treatments)
            if available_treatments and random.random() < 0.6
            else None
        )

        subtotal = (
            treatment.totalCost
            if treatment else Decimal(str(round(random.uniform(100, 3000), 2)))
        )
        discount = (
            Decimal(str(round(random.uniform(0, float(subtotal) * 0.2), 2)))
            if random.random() < 0.3 else Decimal('0.00')
        )

        bill = Bill.objects.create(
            patient=patient,
            treatment=treatment,
            branch=patient.branch,
            description=treatment.title if treatment and treatment.title else faker.text(max_nb_chars=150),
            subtotal=subtotal,
            discount=discount,
            totalAmount=subtotal - discount,
            totalPaid=Decimal('0.00'),
            currency=treatment.currency if treatment else 'EGP',
            createdBy=getattr(patient.doctor, 'name', None),
        )
        attach_visits(bill, patient.id)
        bills.append(bill)
        count += 1

    print(f'  Created {count} bills.')
    return list(Bill.all_objects.all())


def seed_installment_plans(treatments, num_installment_plans=35):
    print('Seeding installment plans...')

    eligible = [
        treatment for treatment in treatments
        if treatment.totalCost is not None and treatment.totalCost > 0
    ]
    selected_plans = random.sample(eligible, min(num_installment_plans, len(eligible)))
    plans = []

    for treatment in selected_plans:
        total = treatment.totalCost
        months = random.choice([1, 3, 6, 12])
        start_date = timezone.localdate(timezone.now()) - timedelta(days=random.randint(30, 60))
        plan = InstallmentPlan.objects.create(
            treatment=treatment,
            branch=treatment.patient.branch,
            installmentMonths=months,
            startDate=start_date,
            totalAmount=total,
            totalPaid=Decimal('0'),
            currency=treatment.currency or 'EGP',
            downPayment=Decimal('0'),
        )
        plans.append(plan)

        amount = (total / months).quantize(Decimal('0.01'))
        for sequence in range(1, months + 1):
            installment_amount = (
                total - amount * (months - 1)
                if sequence == months else amount
            )
            Installment.objects.create(
                installmentPlan=plan,
                amount=installment_amount,
                sequence=sequence,
                dueDate=start_date + timedelta(days=30 * sequence),
                type=Installment.InstallmentTypeChoices.INSTALLMENT,
            )

    print(f'  Created {len(plans)} installment plans and their installments.')
    return plans


def seed_transactions(bills, installment_plans, num_transactions=100):
    print('Seeding transactions...')
    
    #Identify bill type
    bills_no_plan = []
    installment_plan_bills = {}
    for bill in bills:
        if bill.installmentPlan:
            installment_plan_bills[bill.installmentPlan_id] = bill 
        else:
            bills_no_plan.append(bill)

    #Handle non-installment transactions first
    transactions_count = 0
    for _ in range(num_transactions):
        bill = random.choice(bills_no_plan)

        visits = list(bill.visits.all())
        visit = random.choice(visits) if visits and random.random() < 0.4 else None
        transaction_date = faker.date_between(start_date=f'-{2}m', end_date='today')
        amount = Decimal(str(round(random.uniform(50, float(bill.totalAmount)), 2)))
        txn_type = ('visit_fee' if visit else 'treatment_payment' if bill and 
                    (bill.treatment and not bill.installmentPlan) else None)
        method = random.choice(Transaction.PaymentMethodChoices.values)
        method = ('cash' if txn_type == 'deposit' else method)
        refund_reason=faker.text(max_nb_chars=50) if random.random() < 0.08 else None
        correction_reason=faker.text(max_nb_chars=50) if random.random() < 0.12 else None
        status = 'refunded' if refund_reason else 'pending_correction' if correction_reason else 'completed'
        notes = faker.text(max_nb_chars=100) if random.random() < 0.3 else None
        
        #create transaction            
        txn = Transaction(
            bill=bill,
            visit=visit,
            patient=bill.patient,
            branch=bill.branch,
            date=transaction_date,
            amount=amount,
            currency='EGP',
            method=method,
            type=txn_type,
            status=status,
            refundReason=refund_reason,
            correctionReason=correction_reason,
            notes=notes,
            createdBy=getattr(bill.patient.doctor, 'name', None),
        )
        txn.save()
        transactions_count += 1
    
    ########

    #Handle installment plan transactions
    inst_transactions_count = 0
    for plan in installment_plans:

        bill = installment_plan_bills.get(plan.id)
        if not bill:
            continue 
        
        #get installments
        installments = plan.installments.order_by('sequence')

        #identify due installments
        due_installments = [installment for installment in installments 
                            if installment.dueDate <= timezone.localdate(timezone.now())]
        
        pending_installments = due_installments[:random.randint(0, len(due_installments))]

        while pending_installments:
            num_to_settle_per_transaction = random.randint(1, min(2, len(pending_installments)))
            installments_to_pay = pending_installments[:num_to_settle_per_transaction]
            pending_installments = pending_installments[num_to_settle_per_transaction:]

            #transaction details
            amount = sum(installment.amount for installment in installments_to_pay)
            transaction_date = min(timezone.localdate(timezone.now()), installments_to_pay[-1].dueDate + timedelta(days=random.randint(0, 14)))
            method = random.choice(Transaction.PaymentMethodChoices.values)
            refund_reason=faker.text(max_nb_chars=50) if random.random() < 0.025 else None
            correction_reason=faker.text(max_nb_chars=50) if random.random() < 0.075 else None
            status = 'refunded' if refund_reason else 'pending_correction' if correction_reason else 'completed'
            notes = faker.text(max_nb_chars=100) if random.random() < 0.3 else None
            installment_paidAt = timezone.make_aware(datetime.combine(transaction_date, time(hour=random.randint(9, 17))))

            #make transaction to settle selected installments
            txn = Transaction.objects.create(
                    bill=bill,
                    patient=bill.patient,
                    branch=bill.branch,
                    date=transaction_date,
                    amount=amount,
                    currency='EGP',
                    method=method,
                    type='installment',
                    status=status,
                    refundReason=refund_reason,
                    correctionReason=correction_reason,
                    notes=notes,
                    createdBy=getattr(bill.patient.doctor, 'name', None),
                )
            
            #assign transaction and paidAt date
            for installment in installments_to_pay:
                installment.transaction = txn 
                installment.paidAt = installment_paidAt

            #bulk update
            Installment.objects.bulk_update(installments_to_pay, fields=['transaction', 'paidAt'])            

            #increment count
            inst_transactions_count += 1

    print(f'  Created {transactions_count} transactions.')
    print(f'  Created {inst_transactions_count} installment transactions.')
    return list(Transaction.all_objects.all())


def seed_deposits(treatments, num_deposits=15):
    print('Seeding deposit transactions...')
    eligible = [t for t in treatments if t.patient_id]
    if not eligible:
        print('  No eligible treatments for deposits. Skipping.')
        return []

    sample = random.sample(eligible, min(num_deposits, len(eligible)))
    deposits = []
    for treatment in sample:
        amount = Decimal(str(round(random.uniform(200, 2000), 2)))
        deposit = Transaction.autogenerate_deposit_after_reducing_costs_below_paid(
            amount=amount, treatment=treatment
        )
        if random.random() < 0.3:
            deposit.status = 'refunded'
            deposit.refundReason = faker.text(max_nb_chars=50)
            deposit.save(update_fields=['status', 'refundReason'])
        deposits.append(deposit)

    print(f'  Created {len(deposits)} deposit transactions (with dedicated bills).')
    return deposits


def seed_invoices(bills, patients, num_invoices=100):
    '''
    Create invoices individually so that Invoice.save() fires and snapshots bill/patient/branch data.
    '''
    print('Seeding invoices...')
    
    statuses = [
        Invoice.InvoiceStatusChoices.ISSUED,
        Invoice.InvoiceStatusChoices.SUBMITTED,
        Invoice.InvoiceStatusChoices.ACCEPTED,
        Invoice.InvoiceStatusChoices.REJECTED,
    ]

    status_weights = [40, 30, 20, 10]
    tax_codes = [c[0] for c in InvoiceItem.TaxCodeChoices.choices]
    count = 0

    for bill, _ in zip_longest(list(bills), range(num_invoices)):
        if bill:
            #auto-generate invoice from bill
            Bill.generate_invoice(bill=bill)
            count += 1
            continue
        
        #If no bill, generate custom invoice
        bill = None
        patient = random.choice(patients) 
        branch = patient.branch or None
        subtotal = Decimal(str(round(random.uniform(150, 3000), 2)))
        discount = Decimal('0') if random.random() < 0.25 else Decimal(str(round(float(subtotal)*random.uniform(0.05, 0.3), 2)))
        tax = Decimal('0') if random.random() < 0.2 else Decimal(str(round(float(subtotal) * 0.12, 2)))
        total = subtotal + tax - discount

        invoice = Invoice(
            patient=patient,
            bill=bill,
            branch=branch,
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total=total,
            currency='EGP',
            status=random.choices(statuses, weights=status_weights)[0],
            createdBy=getattr(patient.doctor, 'name', None)
        )
        invoice.save()

        InvoiceItem.objects.bulk_create([
            InvoiceItem(
                invoice=invoice,
                taxCode=random.choice(tax_codes) if random.random() < 0.7 else None,
                description=faker.text(max_nb_chars=150),
                quantity=random.randint(1, 3),
                unitPrice=Decimal(str(round(random.uniform(50, 500), 2))),
                total=Decimal(str(round(random.uniform(50, 1000), 2))),
            )
            for _ in range(random.randint(1, 3))
        ])
        count += 1

    print(f'  Created {count} invoices (with items).')
    return list(Invoice.all_objects.all())


def seed_waiting_room(appointments, num_entries=10):
    '''
    Create waiting room entries for past appointments.
    '''
    print('Seeding waiting room...')

    #Only attach to past completed/confirmed appointments
    eligible = [a for a in appointments if a.status in ('completed', 'confirmed') and a.date < timezone.localdate(timezone.now())]
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
            branch=doctor.branch,
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
        except (DoctorSchedule.DoesNotExist, Http404):
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
def run_seed(num_users=10, num_patients=80, num_visits=150,num_appointments=120, num_treatment_plans=60, 
        num_perio_exams_per_patient=5, num_recalls=60, num_inbound_referrals=40, num_outbound_referrals=30, 
        num_lab_orders=40, num_bills=70, num_transactions=100, num_deposits=15, num_installment_plans=35, 
        num_invoices=100, num_waiting_room=10, num_schedule_exceptions=30, num_sterilization_logs=50):

    print('\n', '=' * 50)
    print('  Starting data seeding...')
    print('=' * 50, '\n')

    #Clear existing data in reverse dependency order
    print('Clearing existing data...')
    Patient.all_objects.all().delete()   # cascades to DentalChart, XRay, PatientDocument, & PerioExam
    Visit.all_objects.all().delete()
    Appointment.all_objects.all().delete()
    TreatmentPlan.all_objects.all().delete()
    PatientRecall.all_objects.all().delete()
    InboundReferral.all_objects.all().delete()
    OutboundReferral.all_objects.all().delete()
    Procedure.objects.all().delete()
    Inventory.objects.all().delete()
    DoctorSchedule.all_objects.all().delete()  # cascades to DoctorScheduleException
    LabOrder.all_objects.all().delete()
    Lab.all_objects.all().delete()
    Invoice.all_objects.all().delete()   # cascades to InvoiceItem
    InstallmentPlan.all_objects.all().delete()
    Transaction.all_objects.all().delete()
    Bill.all_objects.all().delete()
    ClinicalTaxConfig.all_objects.all().delete()
    InsuranceProvider.objects.all().delete()
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
    insurance_providers = seed_insurance_providers(branches)
    patients = seed_patients(doctors, insurance_providers, num_patients)
    visits = seed_visits(patients, doctors, num_visits)
    appointments = seed_appointments(patients, doctors, procedures, num_appointments)
    treatments = seed_treatment_plans(patients, doctors, procedures, num_treatment_plans)
    seed_perio_exams(patients, doctors, num_perio_exams_per_patient)
    seed_patient_recalls(patients, branches, num_recalls)
    seed_referrals(branches, doctors, patients, num_inbound_referrals, num_outbound_referrals)
    seed_inventory(branches)
    labs = seed_labs(branches)
    seed_lab_orders(labs, patients, procedures, branches, num_lab_orders)
    seed_clinical_tax_configs(branches)
    installment_plans = seed_installment_plans(treatments, num_installment_plans)
    bills = seed_bills(visits, treatments, installment_plans, num_bills)
    seed_transactions(bills, installment_plans, num_transactions)
    seed_deposits(treatments, num_deposits)
    seed_invoices(bills, patients, num_invoices)
    seed_waiting_room(appointments, num_waiting_room)
    seed_sterilization_logs(branches, users, num_sterilization_logs)

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
    print(f'  Perio Exams:         {PerioExam.objects.count()}')
    print(f'  Patient Recalls:     {PatientRecall.objects.count()}')
    print(f'  Inbound Referrals:   {InboundReferral.objects.count()}')
    print(f'  Outbound Referrals:  {OutboundReferral.objects.count()}')
    print(f'  Insurance Providers: {InsuranceProvider.objects.count()}')
    print(f'  Patient Coverage:    {PatientCoverage.objects.count()}')
    print(f'  Procedures:          {Procedure.objects.count()}')
    print(f'  Waiting Room:        {WaitingRoom.objects.count()}')
    print(f'  Tax Configs:         {ClinicalTaxConfig.all_objects.count()}')
    print(f'  Bills:               {Bill.objects.count()}')
    print(f'  Transactions:        {Transaction.objects.count()}')
    print(f'  Installment Plans:   {InstallmentPlan.objects.count()}')
    print(f'  Invoices:            {Invoice.objects.count()}')
    print(f'  Inventory Items:     {Inventory.objects.count()}')
    print(f'  Low Stock Items:     {Inventory.objects.filter(currentStock__lt=F("minStock")).count()}')
    print(f'  Labs:                {Lab.objects.count()}')
    print(f'  Lab Orders:          {LabOrder.objects.count()}')
    print(f'  Sterilization Logs:  {SterilizationLog.objects.count()}')
    print('=' * 50, '\n')


if __name__ == '__main__':
    while True:
        try:
            run_seed(
                num_users=25, 
                num_patients=100, 
                num_visits=200,
                num_appointments=120,
                num_treatment_plans=60,
                num_perio_exams_per_patient=5,
                num_recalls=60,
                num_inbound_referrals=40, 
                num_outbound_referrals=30, 
                num_lab_orders=40,
                num_bills=70, 
                num_transactions=100,
                num_deposits=15,
                num_installment_plans=35,
                num_invoices=100,
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
