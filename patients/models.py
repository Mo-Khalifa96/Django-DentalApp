import uuid 
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from django.db import models, transaction
from patients.utils import normalize_phone_number
from utils.exceptions import AppointmentConflictError
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy as _context
from django.core.validators import MinValueValidator, MaxValueValidator
from patients.validators import (validate_phone_number, validate_country_code, image_validators, 
                                 file_validators, validate_toothNumber, FDI_PERMANENT)


#Patient manager
class PatientsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients's data
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)  #filter out soft-deleted patients
    
    @transaction.atomic 
    def delete_patient(self, user, patient):
        '''Custom method to soft-delete patients.'''
        if user.role == 'admin':
            #delete patient's files/images
            self._delete_patient_files(patient)
            patient.delete()

        else:
            #Set is_deleted flag to True
            patient.is_deleted = True
            patient.status = 'inactive'

            #delete patient's files/images
            self._delete_patient_files(patient)

            #delete reminder messages 
            patient.patient_reminders.all().delete()

            #save changes
            patient.save()

        return True 
    
    def _delete_patient_files(self, patient):
            #delete patient's x-rays 
            xrays = patient.patient_xrays.all()
            for xray in xrays:
                xray.image.delete(save=False)
            xrays.delete()  #delete xrays

            #delete patient's documents
            documents = patient.patient_documents.all()
            for doc in documents:
                doc.document.delete(save=False)
            documents.delete()

#PATIENTS MODEL 
class Patient(models.Model):
    class GenderChoices(models.TextChoices):
        MALE = 'male', _('Male')
        FEMALE = 'female', _('Female')

    class StatusChoices(models.TextChoices):
        ACTIVE = 'active', _context('patient_status', 'active')
        INACTIVE = 'inactive', _('inactive')
    
    #Blood type choices
    bloodTypeChoices = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-')
    ]


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to the User model (i.e., many patients, one doctor)
    doctor = models.ForeignKey('users.User', related_name='doctor_patients', on_delete=models.SET_NULL, null=True, blank=True, db_index=False)
    #Many-to-One relationship to the Branch model (i.e., many patients, one branch)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_patients', blank=True, null=True, on_delete=models.SET_NULL, db_index=False)
    #Patient fields 
    name = models.CharField(max_length=255)
    age = models.IntegerField(blank=False, null=False)
    gender = models.CharField(max_length=50, choices=GenderChoices.choices)
    countryCode = models.CharField(max_length=6, validators=[validate_country_code])
    phone = models.CharField(max_length=50, validators=[validate_phone_number])
    email = models.EmailField(unique=False, blank=True, null=True)
    nationalId = models.CharField(max_length=120, blank=True, null=True)
    address = models.CharField(max_length=300, blank=True, null=True)
    bloodType = models.CharField(max_length=5, choices=bloodTypeChoices, blank=True, null=True)
    allergies = ArrayField(models.CharField(max_length=255), default=list, blank=True, null=True)
    lastVisit = models.DateField(blank=True, null=True)
    nextAppointment = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=StatusChoices.choices, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    referredByName = models.CharField(max_length=300, blank=True, null=True)
    referredBy = models.ForeignKey('patients.InboundReferral', related_name='referred_patients',
                                on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    
    #other fields
    doctorName = models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)   #Soft delete field


    #Objects after filtering by manager
    objects = PatientsManager()

    #to access all objects
    all_objects = models.Manager()

    #Has reverse relations to the each of the models below (except inventory)
    #Accessible via:
     # patient.patient_visits.all() for related_name='patient_visits' on Visit
     # patient.patient_dentalchart.all() for related_name='patient_dentalchart' on DentalChart
     # patient.patient_appointments.all() for related_name='patient_appointments' on Appointment
     # patient.patient_treatmentplans.all() for related_name='patient_treatmentplans' on TreatmentPlan
     # patient.patient_reminders.all() for related_name='patient_reminders' on Message
     # patient.patient_xrays.all() for related_name='patient_xrays' on Xray

    class Meta:
        db_table = 'Patients'
        verbose_name_plural = 'Patients'
        ordering = ['branch__name', 'name']
        indexes = [
            models.Index(fields=['doctor'], name='patient_doctor_indx', condition=Q(is_deleted=False)),
            models.Index(fields=['branch'], name='patient_branch_indx', condition=Q(is_deleted=False)),
            models.Index(fields=['name'], name='patient_name_indx', condition=Q(is_deleted=False)),
            models.Index(fields=['phone'], name='patient_phone_indx', condition=Q(is_deleted=False)),
            models.Index(fields=['branch', 'name'], name='patient_name_branch_indx', condition=Q(is_deleted=False))
        ]

    def __str__(self):
        return self.name 
    
    @transaction.atomic 
    def save(self, provider=None, *args, **kwargs):
        #assign flag for new patients
        is_new = self._state.adding
        if is_new and not self.status:
            self.status = 'active'
        #Normalize and save phone number
        if self.countryCode and self.phone:
            code, phone_number = normalize_phone_number(self.countryCode, self.phone)
            self.countryCode = code
            #store phone in the format: +10 1234567890
            self.phone = f'{code}{phone_number}'  #NOTE - to normalize for display, you can now do this: phone = '0' + patient.phone[len(patient.countryCode):]  

        if self.doctor:
            #assign current doctor's name
            self.doctorName = self.doctor.name
        
            #fallback condition for branch identification
            # if not self.branch:
            #     self.branch = self.doctor.branch

        if self.referredBy:
            self.referredByName = self.referredBy.name
        else:
            self.referredByName = None

        #save patient to database 
        super().save(*args, **kwargs)

        if is_new:
            #create basic dental chart for new patient
            DentalChart.objects.create(patient=self,
                teeth={tooth:{'status': 'healthy', 'notes': ''}
                        for tooth in FDI_PERMANENT})
            
            #create empty insurance coverage record
            provider = provider or None
            PatientCoverage.objects.create(patient=self, provider=provider)


#Dental Chart manager
class DentalChartManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients's data
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False) 

#DENTAL CHART MODEL 
class DentalChart(models.Model):
    class ToothStatusChoices(models.TextChoices):
        HEALTHY = 'healthy', 'Healthy'
        CAVITY = 'cavity', 'Cavity'
        FILLING = 'filling', 'Filling'
        CROWN = 'crown', 'Crown'
        ROOT_CANAL = 'rct', 'Root Canal'
        VENEER = 'veneer', 'Veneer'
        EXTRACTION = 'extraction', 'Extraction'
        IMPLANT = 'implant', 'Implant'
        MISSING = 'missing', 'Missing'
        WATCH = 'watch', 'Watch'
    
    class ToothSurfacesChoices(models.TextChoices):
        M = 'M', 'mesial'
        D = 'D', 'distal'
        F = 'F', 'facial'
        B = 'B', 'buccal'
        L = 'L', 'lingual'
        P = 'P', 'palatal'
        O = 'O', 'occlusal'
        I = 'I', 'incisal'
    
    #One-to-One relationship to the Patient model (i.e. one dental chart, one patient)
    patient = models.OneToOneField(Patient, related_name='patient_dentalchart', on_delete=models.CASCADE, db_index=True)    
    teeth = models.JSONField()  #Dictionary with nested dictionaries
    # surfaces = ArrayField(models.CharField(max_length=255), default=list, blank=True, null=True)
    lastUpdated = models.DateTimeField(auto_now=True)

    #Objects after filtering by manager
    objects = DentalChartManager()

    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'DentalChart'
        verbose_name_plural = 'DentalChart'
        ordering = ['-lastUpdated']


#Periodontal Exams Manager
class PerioExamsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(patient__is_deleted=False)

#PERIODONTAL EXAMS MODEL
class PerioExam(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    #Many-to-One relationship to Patient (i.e., many exams, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_perio_exams', on_delete=models.CASCADE, db_index=True)
    #Many-to-One relationship to the examining doctor
    examinedBy = models.ForeignKey('users.User', related_name='doctor_perio_exams', on_delete=models.SET_NULL, null=True, db_index=True)
    examinedByName = models.CharField(max_length=255, blank=True, null=True)   #snapshot field
    examinedAt = models.DateField()  #exam's date

    #teeth dict
    teeth = models.JSONField(default=dict)  #{"16": {"mobility": 1, "furcation": 0, "sites": {"DB": {...}, ...}}}

    #summary fields (computed at save time)
    meanProbingDepth = models.FloatField(null=True, blank=True)
    bleedingPercent = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    sitesProbed = models.IntegerField(default=0)

    #other fields
    notes = models.TextField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)  #used for sorting/validating same-day corrections

    #Objects after filtering by manager
    objects = PerioExamsManager()
    #to access all objects   
    all_objects = models.Manager()

    class Meta:
        db_table = 'PerioExams'
        verbose_name_plural = 'PerioExams'
        ordering = ['-examinedAt', '-createdAt']   #newest first, matches contract

    def __str__(self):
        return f'Perio exam for {self.patient.name} on {self.examinedAt}'
    
    @classmethod
    def compute_perio_summary(cls, teeth):
        #prepare summary data
        probingDepth_total = 0 
        probingDepth_count = 0
        bleeding_count = 0
        sites_count = 0
        
        for tooth_dict in teeth.values():
            for site_data in tooth_dict.get('sites', {}).values():
                #compute probing depth total/count
                probing_depth = site_data.get('probingDepth')
                if probing_depth is not None:
                    sites_count += 1  #num sites examined/probed
                    probingDepth_total += probing_depth
                    probingDepth_count += 1

                #compute bleeding count
                if site_data.get('bleeding'):
                    bleeding_count += 1

        #compute mean probing depth and bleeding percent
        probingDepth_mean = round(probingDepth_total / probingDepth_count, 1) if probingDepth_count else None        
        bleeding_perc = int((bleeding_count * 100 / sites_count) +0.5) if sites_count else None  #rounds .5s up
        
        #return results
        return (sites_count, probingDepth_mean, bleeding_perc)


#Visits Manager 
class VisitsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients's data
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False)

#VISITS HISTORY MODEL
class Visit(models.Model):
    class VisitTypeChoices(models.TextChoices):
        ROUTINE_CHECKUP = 'routine_checkup', _('Routine Checkup')
        FOLLOW_UP = 'follow_up', _('Follow up')
        EMERGENCY = 'emergency', _('Emergency')
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to the User model (i.e., many visits, one doctor)
    doctor = models.ForeignKey('users.User', related_name='doctor_visits', on_delete=models.SET_NULL, null=True, db_index=True)
    #Many-to-One relationship to the Patient model (i.e., many visits, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_visits', on_delete=models.CASCADE, db_index=True)

    #Other visit fields
    date = models.DateField()
    type = models.CharField(max_length=50, choices=VisitTypeChoices.choices)
    procedures = ArrayField(models.CharField(max_length=500), default=list)
    cost = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    paid = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)  
    currency = models.CharField(max_length=5, blank=True, null=True)
    xray = models.BooleanField(default=False)  # xrayUrls will be served by serializer using 'patient' field and rel. to Xray
    notes = models.TextField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)

    #snapshot-field for doctor name
    doctorName = models.CharField(max_length=255, blank=True, null=True)


    #Objects after filtering by manager
    objects = VisitsManager()

    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'Visits'
        verbose_name_plural = 'Visits'
        ordering = ['-createdAt', 'patient__name']
        indexes = [
            models.Index(fields=['patient', 'date']),
        ]

    def __str__(self):
        return f'[{self.date}] {self.type} -- {self.patient.name}'
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding and self.date:
            self.patient.lastVisit = self.date 
            self.patient.save(update_fields=['lastVisit', 'updatedAt'])
        
        #assign current doctor's name
        if self.doctor:
            self.doctorName = self.doctor.name
        
        #save  to database
        super().save(*args, **kwargs)


#X-Rays manager 
class XRaysManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients's data
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False)

#X-Rays model for xray image uploads
class XRay(models.Model):
    #Many-to-One relationship to the Patient and Visit models (i.e., many x-rays, one patient, one visit)
    patient = models.ForeignKey(Patient, related_name='patient_xrays', on_delete=models.CASCADE, db_index=True)
    visit = models.ForeignKey(Visit, related_name='visit_xrays', on_delete=models.CASCADE, db_index=True)
    image = models.ImageField(upload_to='xrays/', validators=image_validators)
    uploadedAt = models.DateTimeField(auto_now_add=True)

    #Objects after filtering by manager
    objects = XRaysManager()

    #to access all objects
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'XRays'
        verbose_name_plural = 'XRays'
        ordering = ['-uploadedAt']
    
    def __str__(self):
        return f'{self.image.url}'


#Patient documents manager
class PatientDocumentsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients's data
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False)

#Patient documents model for document uploads
class PatientDocument(models.Model):
    class DocumentTypeChoices(models.TextChoices):
        CONSENT = 'consent', _('Consent')
        MEDICAL_HISTORY = 'medical_history', _('Medical history')
        ID_DOCUMENT = 'id_document', _('ID document')
        REFERRAL_LETTER = 'referral_letter', _('Referral letter')
        RADIOGRAPH = 'radiograph', _('Radiograph')
        OTHER = 'other', _context('document_type', 'Other')
        
    #Many-to-One relationship to the Patient model (i.e., many documents, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_documents', on_delete=models.CASCADE, db_index=True)
    document = models.FileField(upload_to='documents/', validators=file_validators)
    fileName = models.CharField(max_length=300, blank=True, null=True)
    type = models.CharField(max_length=50, choices=DocumentTypeChoices.choices, blank=True, null=True)
    contentType = models.CharField(max_length=50, blank=True, null=True) 
    sizeBytes = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    uploadedBy = models.CharField(max_length=255, blank=True, null=True) 
    uploadedAt = models.DateTimeField(auto_now_add=True)

    #Objects after filtering by manager
    objects = PatientDocumentsManager()

    #to access all objects
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'PatientDocuments'
        verbose_name_plural = 'PatientDocuments'
        ordering = ['-uploadedAt']
    
    def __str__(self):
        return f'{self.document.url}'


#Appointments Manager 
class AppointmentsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients's data
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False)

#APPOINTMENTS MODEL 
class Appointment(models.Model):
    class AppointmentStatusChoices(models.TextChoices):
        PENDING = 'pending', _('pending')
        CONFIRMED = 'confirmed', _('confirmed')
        COMPLETED = 'completed', _('completed')
        CANCELLED = 'cancelled', _('cancelled')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to the User model (i.e., many appointments, one doctor)
    doctor = models.ForeignKey('users.User', related_name='doctor_appointments', on_delete=models.SET_NULL, null=True, db_index=True)
    #Many-to-One relationship to the Patient model (i.e., many appointments, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_appointments', on_delete=models.CASCADE, db_index=True)
    #Many-to-One relationship to the Procedure model (i.e., many appointments, one procedure) -- #TODO: may need to change to ManyToMany(); to be confirmed...
    procedure = models.ForeignKey('clinic.Procedure', related_name='related_appointments', on_delete=models.SET_NULL, null=True, db_index=True)
    #Many-to-One relationship to the Branch model (i.e., many appointments, one branch)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_appointments', blank=True,
                                null=True, on_delete=models.SET_NULL, db_index=True)
    #Other appointment fields
    date = models.DateField(db_index=True)
    startTime = models.TimeField()
    endTime = models.TimeField(blank=True, null=True)
    type = models.CharField(max_length=500, choices=Visit.VisitTypeChoices.choices)
    room = models.CharField(max_length=120, blank=True, null=True)
    status = models.CharField(max_length=50, choices=AppointmentStatusChoices.choices, db_index=True)
    notes = models.TextField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    #snapshot fields to preserve fields when foreignkey is deleted
    procedureName = models.CharField(max_length=255, blank=True, null=True)
    doctorName = models.CharField(max_length=255, blank=True, null=True)

    #Objects after filtering by manager
    objects = AppointmentsManager()

    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'Appointments'
        verbose_name_plural = 'Appointments'
        ordering = ['branch__name', '-createdAt', 'patient__name']
        indexes = [  #optimizes fields that are often queried together
            models.Index(fields=['branch', 'date']),
            models.Index(fields=['doctor', 'date', 'status']), 
        ]

    def __str__(self):
        return f"[{self.date} {self.startTime}{(' - '+str(self.endTime.strftime('%I:%M %p'))) if self.endTime else ''}] {self.type} -- {self.patient.name}"

    def get_time(self):
        if not self.endTime:
            return f"{self.startTime.strftime('%I:%M %p')}"
        return f"{self.startTime.strftime('%I:%M')} - {self.endTime.strftime('%I:%M %p')}"


    @transaction.atomic 
    def save(self, *args, **kwargs):
        if self._state.adding:
            if not self.status:
                self.status = 'pending'
            self.procedureName = self.procedure.name
            self.doctorName = getattr(self.doctor, 'name', None)

            if self.date:
                #update nextAppointment field on patient
                self.patient.nextAppointment = self.date
                self.patient.save(update_fields=['nextAppointment', 'updatedAt'])

        #save appointment to database 
        super().save(*args, **kwargs)


    @classmethod
    def validate_availability(cls, doctorId, branchId, date, startTime, endTime, current_id=None):
        '''Validates appointment availability. Raises conflict error when appointment time slot is taken.'''
        
        #Get appointments by provided date 
        appointments_byDate = cls.objects.only(
            'id', 'patient', 'doctor_id', 'branch_id', 'date', 'startTime', 'endTime', 'status'
         ).filter(
             doctor_id=doctorId,
             date=date, 
             status__in=['pending', 'confirmed', 'completed']  #ignore cancelled
        )
        
        if branchId:  #NOTE: checking here is restricted by branch; but conflicts may be evident across branches
            appointments_byDate = appointments_byDate.filter(branch_id=branchId)

        if current_id:
            appointments_byDate = appointments_byDate.exclude(id=current_id)

        conflict = None 
        if not endTime:
            conflict = appointments_byDate.filter(
                Q(startTime=startTime, endTime__isnull=True) |
                Q(startTime__lte=startTime, endTime__gt=startTime)
            ).select_related('patient', 'branch').first()
        else:
            conflict = appointments_byDate.filter(
                startTime__lt=endTime, endTime__gt=startTime
            ).select_related('patient', 'branch').first()
        
        if conflict:
            error_details = {
                'conflictWith': {
                    'appointmentId': conflict.id,
                    'branchId': getattr(conflict.branch, 'id', None),
                    'patientName': conflict.patient.name,
                    'time': conflict.get_time()
                }
            }

            raise AppointmentConflictError(error_details)
        
        return True


#Treatment Plans Manager 
class TreatmentPlansManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients's data
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False) 

#TREATMENT PLANS MODEL 
class TreatmentPlan(models.Model):
    class TreatmentStatusChoices(models.TextChoices):
        ACTIVE = 'active', _context('treatment_status', 'active')
        COMPLETED = 'completed', _('completed')
        CANCELLED = 'cancelled', _('cancelled')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to the User model (i.e., many treatments, one doctor)
    doctor = models.ForeignKey('users.User', related_name='doctor_treatmentplans', on_delete=models.SET_NULL, null=True, db_index=True)
    #Many-to-One relationship to the Patient model (i.e., many treatments, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_treatmentplans', on_delete=models.CASCADE, db_index=True)
    
    #other model fields
    title = models.CharField(max_length=250, blank=True, null=True)
    status = models.CharField(max_length=50, choices=TreatmentStatusChoices.choices, blank=True, null=True)
    currency = models.CharField(max_length=5, blank=True, null=True)
    totalCost = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    # installmentMonths = models.PositiveSmallIntegerField(choices=InstallmentMonthsChoices.choices, blank=True, null=True)
    sessions = models.PositiveSmallIntegerField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    
    #snapshot field for if user is deleted
    doctorName = models.CharField(max_length=255, blank=True, null=True)

    #Objects after filtering by manager
    objects = TreatmentPlansManager()

    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'TreatmentPlans'
        verbose_name_plural = 'TreatmentPlans'
        ordering = ['-createdAt', 'patient__name']

    @transaction.atomic
    def save(self, *args, **kwargs):
        #if creating treatment plan but not a doctor, assign doctor
        if self._state.adding:
            if not self.status:
                self.status = 'active'
            if self.patient and not self.doctor and self.patient.doctor:
                self.doctor = self.patient.doctor
            if self.doctor:
                self.doctorName = self.doctor.name
        #save changes 
        super().save(*args, **kwargs)

#TREATMENT PLAN ITEMS MODEL -- supplements the TreatmentPlan model 
class TreatmentPlanItem(models.Model):
    class ItemStatusChoices(models.TextChoices):
        PENDING = 'pending', _('pending')
        IN_PROGRESS = 'in_progress', _('in progress')
        COMPLETED = 'completed', _('completed')
        
    #Many-to-One relationship to the TreatmentPlan model (i.e., many items, one treatmentPlan)
    treatmentPlan = models.ForeignKey(TreatmentPlan, related_name='treatment_items', on_delete=models.CASCADE, db_index=True)
    #Many-to-One relationship to the Procedure model (i.e., many items can reference the same procedure)
    procedure = models.ForeignKey('clinic.Procedure', related_name='treatment_items', on_delete=models.SET_NULL, null=True)
    toothNumber = models.CharField(max_length=3, blank=True, null=True, validators=[validate_toothNumber])
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    session = models.PositiveSmallIntegerField(blank=True, null=True)
    status = models.CharField(max_length=25, choices=ItemStatusChoices.choices, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    #snapshot field to preserve procedure name when foreignkey is deleted
    procedureName = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'TreatmentPlanItems'
        verbose_name_plural = 'TreatmentPlanItems'

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding and not self.status:
            self.status = 'pending'
         #save changes 
        super().save(*args, **kwargs)


#Patient Coverage Manager
class PatientCoverageManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False) 

#PATIENT COVERAGE MODEL (insurance coverage)
class PatientCoverage(models.Model):
    class EligibilityStatusChoices(models.TextChoices):
        ACTIVE = 'active', _context('insurance_status', 'Active')
        EXPIRING = 'expiring', _('Expiring')
        EXPIRED = 'expired', _('Expired')
        LIMIT_REACHED = 'limit_reached', _('Limit Reached')
        NONE = 'none', _('None')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #One-to-One relationship to the Patient model (i.e. one patient, one insurance)
    patient = models.OneToOneField(Patient, related_name='patient_insurance', on_delete=models.CASCADE, db_index=True)
    #Many-to-One relationships to InsuranceProvider (i.e., many coverages, one provider)
    provider = models.ForeignKey('finances.InsuranceProvider', related_name='provider_coverages', 
                  on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    providerName = models.CharField(max_length=300, blank=True, null=True)

    memberId = models.CharField(max_length=100, blank=True, null=True)
    annualMax = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    usedYTD = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    deductibleMet = models.BooleanField(blank=True, null=True)
    coveragePercent = models.IntegerField(blank=True, null=True)
    currency = models.CharField(max_length=5, blank=True, null=True)
    
    effectiveFrom = models.DateField(null=True, blank=True)
    effectiveTo = models.DateField(null=True, blank=True)  
    
    eligibilityStatus = models.CharField(max_length=25, choices=EligibilityStatusChoices.choices, blank=True, null=True)
    eligibilityChecked = models.DateField(null=True, blank=True)
    
    updatedAt = models.DateTimeField(auto_now=True)

    #Objects after filtering by manager
    objects = PatientCoverageManager()
    
    #to access all objects
    all_objects = models.Manager()

    class Meta: 
        db_table = 'PatientCoverage'
        verbose_name_plural = 'PatientCoverage'
        ordering = ['eligibilityStatus', 'patient__branch__name', 'patient__name']
        indexes = [
            models.Index(fields=['patient', 'provider'])
        ]

    def __str__(self):
        return f'[{self.effectiveFrom} - {self.effectiveTo}] {self.patient.name} -- {self.providerName} insurance'

    @transaction.atomic
    def save(self, *args, **kwargs):
        #handle provider-related information
        if self.provider:
            self.providerName = self.provider.name

            #determine annual max from provider
            if not self.annualMax and self.provider.annualMax:
                self.annualMax = self.provider.annualMax

            #determine coverage percent
            if not self.coveragePercent:
                self.coveragePercent = self.provider.coveragePercent

            #determine if deducible is met
            if not self.deductibleMet:
                self.deductibleMet = self.deductibleMet if (self.coveragePercent != 100) else True

            #check if the allowance has been used up 
            if isinstance(self.usedYTD, Decimal) and isinstance(self.annualMax, Decimal):
                if self.usedYTD >= self.annualMax:
                    self.eligibilityStatus = 'limit_reached'
                    self.eligibilityChecked = timezone.localdate(timezone.now())
                elif self.eligibilityStatus == 'limit_reached':  #to account for refunds
                    self.eligibilityStatus = 'active'
                    self.eligibilityChecked = timezone.localdate(timezone.now())

        #handle null usedYTD
        if self.usedYTD in (None, ''):
            self.usedYTD = Decimal('0')

        #handle status
        if not self.eligibilityStatus:
            self.eligibilityStatus = 'none'

        #save changes 
        super().save(*args, **kwargs)

    def validate_coverage_for_transaction(self, transaction_amount):
        '''Validates patient insurance can coverage transaction costs.'''

        #validate if patient has a provider
        if not self.provider: #or (coverage.providerName and not (isinstance(coverage.annualMax, Decimal) or isinstance(coverage.usedYTD, Decimal))):
            raise serializers.ValidationError({'method': _(f'The current patient is not associated with any known insurance provider. ' #or has an outdated coverage plan. '
                                                           f'Either update their insurance details or change the transaction method to complete the transaction.')})

        #validate if insurance coverage still active
        if self.eligibilityStatus == PatientCoverage.EligibilityStatusChoices.EXPIRED:
            raise serializers.ValidationError({'method': _(f"The current patient's insurance coverage is expired. "
                                                           f"Either update their insurance details or change the transaction method to complete the transaction.")})
        
        #validate if coverage's limit is reached / maxed out
        elif self.eligibilityStatus == PatientCoverage.EligibilityStatusChoices.LIMIT_REACHED:
            raise serializers.ValidationError({'method': _(f"The current patient's insurance coverage has reached the maximum allowance from their insurer. "
                                                           f"Either update their insurance details or change the transaction method to complete the transaction.")})

        #validate if deductible required for insurance benefits is met
        elif isinstance(self.coveragePercent, int) and (self.coveragePercent < 100 ) and (self.deductibleMet == False):
            raise serializers.ValidationError({'method': _(f"The current patient didn't meet the minimum deductible amount required to activate their insurance coverage. "
                                                           f"Either update their insurance details or change the transaction method to complete the transaction.")})

        #validate the transaction amount doesn't exceed the coverage's annual max
        if isinstance(self.annualMax, Decimal) and isinstance(self.usedYTD, Decimal)\
            and (self.usedYTD + transaction_amount > self.annualMax):
            raise serializers.ValidationError({'method': _(f"The transaction amount exceeds the maximum allowed by the patient's insurance coverage ({self.annualMax})"
                                                           f"given their yearly usage to date ({self.usedYTD}). "
                                                           f"Either divide the payment into different transactions and/or change the transaction method to complete the transaction.")})
    
        return True


#Patient Recalls Manager
class PatientRecallsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False) 

#PATIENT RECALLS MODEL 
class PatientRecall(models.Model):
    class RecallTypeChoices(models.TextChoices):
        CHECKUP = 'checkup', _('Checkup')
        POST_PROCEDURE = 'post_procedure', _('Post-procedure')
        TREATMENT = 'treatment', _('Treatment')
        CUSTOM = 'custom', _('Custom')
    
    class RecallStatusChoices(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONTACTED = 'contacted', _('Contacted')
        CONFIRMED = 'confirmed', _('Confirmed')
        NO_ANSWER = 'no_answer', _('No answer')
        DECLINED = 'declined', _('Declined')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to the Patient model (i.e., many recalls, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_recalls', on_delete=models.CASCADE, db_index=True)
    #Many-to-One relationship to the Branch model (i.e., many recalls, one branch)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_patient_recalls', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)  #Changed cascade to set_null
    #other fields
    phone = models.CharField(max_length=50, blank=True, null=True, validators=[validate_phone_number])
    type = models.CharField(max_length=50, choices=RecallTypeChoices.choices)
    status = models.CharField(max_length=50, choices=RecallStatusChoices.choices, blank=True, null=True)
    dueDate = models.DateField()
    notes = models.TextField(blank=True, null=True)
    contactedAt = models.DateTimeField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    #Objects after filtering by manager
    objects = PatientRecallsManager()
    
    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'PatientRecalls'
        verbose_name_plural = 'PatientRecalls'
        ordering = ['branch__name', 'patient__name']
        indexes = [
            models.Index(fields=['patient', 'branch']),
            models.Index(fields=['patient', 'branch', 'status']),
        ]
        # constraints = [
        #     models.UniqueConstraint(
        #         fields=['patient', 'type'],
        #         condition=Q(status='pending'),
        #         name='unique_pending_recall_per_patient_and_type'
        #     )
        # ]

    def __str__(self):
        return f'{self.type} for patient {self.patient.name}'
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding:
            if not self.status:
                self.status = 'pending'
            if not self.phone:
                self.phone = self.patient.phone
        
        #if status is contacted, set contact date to today
        if self.status == 'contacted' and not self.contactedAt:
            self.contactedAt = timezone.localtime(timezone.now())

        #save changes 
        super().save(*args, **kwargs)
        

#REFERRALS
#Inbound Referrals Manager -- linked to branch since patients are referred to this branch/clinic
class InboundReferralsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
                models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False),
                isDeleted=False
            )

    @transaction.atomic
    def delete_referral(self, user, referral):
        '''Custom method to soft-delete referrals.'''
        if user.role == 'admin':
            referral.delete()   #Patient.referredBy falls back to SET_NULL
        else:
            referral.isDeleted = True
            referral.save(update_fields=['isDeleted'])
        return True

#INBOUND REFERRALS MODEL  -- patients referred from outside source to clinic
class InboundReferral(models.Model):
    class SpecialityChoices(models.TextChoices):
        GENERAL = 'general', _('General')
        ORTHODONTICS = 'orthodontics', _('Orthodontics')
        ORAL_SURGERY = 'oral_surgery', _('Oral Surgery') 
        ENDODONTICS = 'endodontics', _('Endodontics')
        PERIODONTICS = 'periodontics', _('Periodontics') 
        PROSTHODONTICS = 'prosthodontics', _('Prosthodontics') 
        PEDIATRIC = 'pediatric', _('Pediatric') 
        RADIOLOGY = 'radiology', _('Radiology') 
        OTHER = 'other', _context('speciality_choice', 'Other')

    #model fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to the User and Branch models (i.e., many inbound-referrals, one doctor, one branch)
    referredByUser = models.ForeignKey('users.User', related_name='doctor_outbound_referrals', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_inbound_referrals',   #NOTE: this is the RECEIVING branch
                               blank=True, null=True, on_delete=models.SET_NULL, db_index=True) 
    name = models.CharField(max_length=300, null=True)  #NULL for auto-assignment
    clinic = models.CharField(max_length=255, blank=True, null=True)
    speciality = models.CharField(max_length=32, choices=SpecialityChoices.choices)
    phone = models.CharField(max_length=50, blank=True, null=True, validators=[validate_phone_number])
    email = models.EmailField(unique=False, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    isDeleted = models.BooleanField(default=False)

    #Objects after filtering by manager
    objects = InboundReferralsManager()
    
    #to access all objects
    all_objects = models.Manager()

    class Meta: 
        db_table = 'InboundReferrals'
        verbose_name_plural = 'InboundReferrals'
        ordering = ['branch__name', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['referredByUser', 'branch'],   #On user as referral source per branch
                condition=models.Q(referredByUser__isnull=False),
                name='unique_referredByUser_per_branch'
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.speciality})'

    @transaction.atomic
    def save(self, *args, **kwargs):
        #handle name and email auto-assignment (on create & update)
        if self.referredByUser:
            self.name = self.referredByUser.name
            self.email = self.referredByUser.email
            self.clinic = None

        #save changes 
        super().save(*args, **kwargs)


#Outbound Referrals Manager -- linked to patient since they concern the clinic's current patients
class OutboundReferralsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False) 

#OUTBOUND REFERRALS MODEL -- patients referred from clinic to outside source
class OutboundReferral(models.Model):
    class ReferralStatusChoices(models.TextChoices):
        SENT = 'sent', _('Sent')
        SCHEDULED = 'scheduled', _('Scheduled')
        COMPLETED = 'completed', _('Completed')
        DECLINED = 'declined', _('Declined')
    
    #model fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to Branch, Patient, User, InboundReferral models (i.e., many outbound-referrals, one branch, one patient, one doctor, one referral)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_outbound_referrals', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)  #Changed cascade to set_null
    patient = models.ForeignKey(Patient, related_name='patient_outbound_referrals', on_delete=models.CASCADE, db_index=True)
    referredToUser = models.ForeignKey('users.User', related_name='doctor_inbound_referrals', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    referredToEntity = models.ForeignKey(InboundReferral, related_name='entity_outbound_referrals', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    name = models.CharField(max_length=300, null=True)
    status = models.CharField(max_length=25, choices=ReferralStatusChoices.choices, blank=True, null=True)
    outcome = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    #Objects after filtering by manager
    objects = OutboundReferralsManager()
    
    #to access all objects
    all_objects = models.Manager()

    class Meta: 
        db_table = 'OutboundReferrals'
        verbose_name_plural = 'OutboundReferrals'
        ordering = ['branch__name', '-updatedAt']
        constraints = [
         models.CheckConstraint(
            #both fields CANNOT be set (not NULL) at the same time -- either one or the other or neither
            condition=~(Q(referredToUser__isnull=False) & Q(referredToEntity__isnull=False)),
            name='outbound_referral_single_target'
         )
        ]

    def __str__(self):
        return f'{self.patient.name} referred to {self.name}'

    @transaction.atomic
    def save(self, *args, **kwargs):
        #Auto-assign status on create (if not provided)
        if self._state.adding and not self.status:
            self.status = 'sent'
        
        #handle name assignment (create & update)
        if self.referredToUser:
            self.name = self.referredToUser.name
        elif self.referredToEntity:
            self.name = self.referredToEntity.name

        #save changes
        super().save(*args, **kwargs)
