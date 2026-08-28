import uuid 
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from django.db import models, transaction
from patients.utils import normalize_phone_number
from utils.exceptions import AppointmentConflictError
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy as _context
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
            self.status = self.StatusChoices.ACTIVE
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
        OTHER = 'other', _('Other')
        
    #Many-to-One relationship to the Patient model (i.e., many documents, one patient)
    patient = models.ForeignKey(Patient, related_name='patient_documents', on_delete=models.CASCADE, db_index=True)
    document = models.FileField(upload_to='documents/', validators=file_validators)
    fileName = models.CharField(max_length=125)
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
                self.status = self.AppointmentStatusChoices.PENDING
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
    
    class InstallmentMonthsChoices(models.IntegerChoices):
        FULL_PAYMENT = 1, _('Full payment')
        THREE_MONTHS = 3, _('3 months')
        SIX_MONTHS = 6, _('6 months')
        TWELVE_MONTHS = 12, _('12 months')

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
    installmentMonths = models.PositiveSmallIntegerField(choices=InstallmentMonthsChoices.choices, blank=True, null=True)
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
                self.status = self.TreatmentStatusChoices.ACTIVE
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
            self.status = self.ItemStatusChoices.PENDING
         #save changes 
        super().save(*args, **kwargs)


#Patient Recalls Manager
class PatientRecallsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted patients
    def get_queryset(self): 
        return super().get_queryset().filter(patient__is_deleted=False) 

#PATIENT RECALL MODEL 
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
    branch = models.ForeignKey('clinic.Branch', related_name='branch_patient_recalls', on_delete=models.CASCADE, blank=True, null=True, db_index=True)
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
                self.status = self.RecallStatusChoices.PENDING
            if not self.phone:
                self.phone = self.patient.phone
        
        #if status is contacted, set contact date to today
        if self.status == self.RecallStatusChoices.CONTACTED and not self.contactedAt:
            self.contactedAt = timezone.localtime(timezone.now())

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
        NONE = 'none', _('None')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #One-to-One relationship to the Patient model (i.e. one patient, one insurance)
    patient = models.OneToOneField(Patient, related_name='patient_insurance', on_delete=models.CASCADE, db_index=True)
    #Many-to-One relationships to InsuranceProvider (i.e., coverages, one provider)
    provider = models.ForeignKey('finances.InsuranceProvider', related_name='provider_coverages', 
                  on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    providerName = models.CharField(max_length=300, blank=True, null=True)

    memberId = models.CharField(max_length=100, blank=True, null=True)
    annualMax = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    usedYTD = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    deductibleMet = models.BooleanField(blank=True, null=True)
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
        #handle annualMax
        if self.provider:
            self.providerName = self.provider.name
            if not self.annualMax and self.provider.annualMax:
                self.annualMax = self.provider.annualMax

        #handle status
        if not self.eligibilityStatus:
            self.eligibilityStatus = self.EligibilityStatusChoices.NONE
        
        #save changes 
        super().save(*args, **kwargs)
