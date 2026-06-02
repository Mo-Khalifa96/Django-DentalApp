import uuid 
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from patients.validators import validate_phone_number, validate_toothNumber


#Choices class for mapping working day numbers to day labels
class WorkingDaysLookUp(models.IntegerChoices):  #Access all week numbers at once with WorkingDaysLookUp.values; and all week names at once with WorkingDaysLookUp.labels
    SUNDAY = 0, _('Sunday')  #access week number via choice.value; and week name via choice.label
    MONDAY = 1, _('Monday') 
    TUESDAY = 2, _('Tuesday')
    WEDNESDAY = 3, _('Wednesday')
    THURSDAY = 4, _('Thursday')
    FRIDAY = 5, _('Friday')
    SATURDAY = 6, _('Saturday')


#Branch manager (allows soft deleting)
class BranchManager(models.Manager):
    #Filter out soft-deleted branches
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
    @transaction.atomic 
    def delete_branch(self, branch):
        '''Custom method to soft-delete branches.'''
        #Set is_deleted flag to True 
        branch.is_deleted = True
        #other code...
        #save changes
        branch.save()
        return True 


#BRANCH MODEL
class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=50, validators=[validate_phone_number])
    workingDays = ArrayField(models.IntegerField(choices=WorkingDaysLookUp.choices), default=list)
    openTime = models.TimeField()
    closeTime = models.TimeField()
    isMain = models.BooleanField(default=False)
    rooms = ArrayField(models.CharField(max_length=50), default=list, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    createdAt = models.DateField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)   #Soft delete field

    #Objects after filtering by manager
    objects = BranchManager()

    #to access all objects
    all_objects = models.Manager()

    #Has reverse relations to the each of the models below (except inventory)
    #Accessible via:
     # branch.branch_labs.all() for related_name='branch_labs' on Lab
     # branch.branch_users.all() for related_name='branch_users' on User
     # branch.branch_rooms.all() for related_name='branch_rooms' on WaitingRoom
     # branch.branch_patients.all() for related_name='branch_patients' on Patient
     # branch.branch_inventory.all() for related_name='branch_inventory' on Inventory
     # branch.branch_procedures.all() for related_name='branch_procedures' on Procedure
     # branch.branch_appointments.all() for related_name='branch_appointments' on Appointment

    class Meta:
        db_table = 'Branches'
        verbose_name_plural = 'Branches'
        ordering = ['-isMain', 'name']

    def __str__(self):
        return self.name


    @transaction.atomic 
    def save(self, *args, **kwargs):
        if self._state.adding:
            if not self.rooms:
                self.rooms = ['Chair 1'] #assign one chair room 
            if not self.isMain and Branch.objects.count() == 0:
                self.isMain = True  #assign first branch as main
        super().save(*args, **kwargs)


#Waiting Room Manager
class WaitingRoomManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
            Q(branch__isnull=True) | Q(branch__is_deleted=False)
            )

#WAITING ROOM MODEL
class WaitingRoom(models.Model):
    class StatusChoices(models.TextChoices):
        WAITING = 'waiting', _('Waiting')
        IN_CHAIR = 'in_chair', _('In chair')
        DONE = 'done', _('Done')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One Relation to appointment and branch (one appointment, one branch, many waiting room objects)
    appointment = models.ForeignKey('patients.Appointment', related_name='appointment_rooms', on_delete=models.CASCADE, null=True, db_index=True)
    branch = models.ForeignKey(Branch, related_name='branch_rooms', on_delete=models.CASCADE, blank=True, null=True, db_index=True) 
    #Other fields
    room = models.CharField(max_length=120, blank=True, null=True)  #use branch rooms for choices
    status = models.CharField(max_length=25, choices=StatusChoices.choices, default=StatusChoices.WAITING)
    arrivedAt = models.DateTimeField(blank=True, null=True)
    startedAt = models.DateTimeField(blank=True, null=True)
    completedAt = models.DateTimeField(blank=True, null=True)

    #Objects after filtering by manager
    objects = WaitingRoomManager()

    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'WaitingRoom'
        verbose_name_plural = 'WaitingRoom'
        ordering = ['-arrivedAt']

    def __str__(self):
        return f'[{self.arrivedAt}] {self.appointment.patient.name} -- {self.status}'


    @transaction.atomic
    def save(self, *args, **kwargs):
        #Assign dates on creation and updates
        if self._state.adding:
            self.arrivedAt = timezone.localtime(timezone.now())

        if self.status == self.StatusChoices.IN_CHAIR:
            self.startedAt = timezone.localtime(timezone.now())
        elif self.status == self.StatusChoices.DONE:
            self.completedAt = timezone.localtime(timezone.now())
            #also update appointment status
            self.appointment.status = 'completed'
            self.appointment.endTime = self.completedAt.time()
            self.appointment.save(update_fields=['status', 'endTime', 'updatedAt'])

            #set patient's next appointment to null
            self.appointment.patient.nextAppointment = None 
            self.appointment.patient.save(update_fields=['nextAppointment', 'updatedAt'])
        
        #save changes 
        super().save(*args, **kwargs)


#Procedures Manager 
class ProcedureManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
                models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False)
            )

#PROCEDURES MODEL 
class Procedure(models.Model): 
    class ProcedureCategory(models.TextChoices):
        CheckUp = 'routine_checkup', _('Routine Checkup')
        Cosmetic = 'cosmetic', _('Cosmetic')
        Diagnostic = 'diagnostic', _('Diagnostic')
        Endodontic = 'endodontic', _('Endodontic')
        Implant = 'implant', _('Implant')
        Preventive = 'preventive', _('Preventive')
        Prosthetic = 'prosthetic', _('Prosthetic')
        Restorative = 'restorative', _('Restorative')
        Surgical = 'surgical', _('Surgical')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=25, choices=ProcedureCategory.choices)
    duration = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0)])
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=5, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    #Many-to-One relationship to the Branch model (i.e., many procedures, one branch)
    branch = models.ForeignKey(Branch, related_name='branch_procedures', blank=True,
                                null=True, on_delete=models.CASCADE, db_index=True)


    #Objects after filtering by manager
    objects = ProcedureManager()

    #to access all objects
    all_objects = models.Manager()


    #Has reverse relations to Appointment and TreatmentPlan models
    #Accessible via: 
    # procedure.related_appointments.all() for related_name='related_appointments' on Appointment
    # procedure.related_orders.all() for related_name='related_orders' on LabOrder
    # procedure.procedure_treatmentplans.all() for related_name='procedure_treatmentplans' on TreatmentPlan

    class Meta:
        db_table = 'Procedures'
        verbose_name_plural = 'Procedures'
        ordering = ['branch__name', 'name']

    def __str__(self):
        return f'{self.name} ({self.category})'

    # def save(self, *args, **kwargs):
    #     if self._state.adding and not self.branch and\
    #      'branch' in kwargs and kwargs.get('branch'):
    #         self.branch = kwargs['branch']
    #     #save changes 
    #     super().save(*args, **kwargs)
       

#Inventory Manager 
class InventoryManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
                models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False)
            )


#INVENTORY MODEL
class Inventory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    currentStock = models.IntegerField()
    minStock = models.IntegerField()
    unit = models.CharField(max_length=255)
    supplier = models.CharField(max_length=255)
    lastOrdered = models.DateField()
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    #Many-to-One relationship to the Branch model (i.e., many inventory items, one branch)
    branch = models.ForeignKey(Branch, related_name='branch_inventory', blank=True,
                                null=True, on_delete=models.CASCADE, db_index=True)

    #Objects after filtering by manager
    objects = InventoryManager()

    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'Inventory'
        verbose_name_plural = 'Inventory'
        ordering = ['branch__name', 'name']
    
    def __str__(self):
        return f'{self.name} - {self.unit}'
    
    def save(self, *args, **kwargs):
        if self._state.adding and not self.lastOrdered:
            self.lastOrdered = timezone.localdate()
        #save changes 
        super().save(*args, **kwargs)


#Lab Manager 
class LabsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
                models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False)
            )

#LAB MODEL 
class Lab(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, validators=[validate_phone_number])
    address = models.CharField(max_length=500)
    contactPerson = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    #Many-to-One relationship to the Branch model (i.e., many labs, one branch)
    branch = models.ForeignKey(Branch, related_name='branch_labs', blank=True,
                                null=True, on_delete=models.CASCADE, db_index=True)
    
    #Objects after filtering by manager
    objects = LabsManager()
    
    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'Labs'
        verbose_name_plural = 'Labs'
        ordering = ['branch__name', 'name']

    def __str__(self):
        return self.name


#Lab Orders Manager 
class LabOrdersManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
                models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False)
            )

#LAB ORDER MODEL
class LabOrder(models.Model):
    class OrderStatusChoices(models.TextChoices):
        SENT = 'sent', _('Sent')
        IN_PRODUCTION = 'in_production', _('In production')
        DELIVERED = 'delivered', _('Delivered')
        RECEIVED = 'received', _('Received')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relations to lab, patient, procedure, and branch (one lab/patient/procedure/branch, many orders)
    lab = models.ForeignKey(Lab, related_name='lab_orders', on_delete=models.SET_NULL, null=True, db_index=True)
    procedure = models.ForeignKey(Procedure, related_name='related_orders', on_delete=models.SET_NULL, null=True, db_index=True)
    patient = models.ForeignKey('patients.Patient', related_name='patient_lab_orders', on_delete=models.SET_NULL, null=True, db_index=True)
    branch = models.ForeignKey(Branch, related_name='branch_lab_orders', on_delete=models.CASCADE, blank=True, null=True, db_index=True)

    #other model fields
    toothNumber = models.CharField(max_length=3, validators=[validate_toothNumber])
    instructions = models.CharField(max_length=500, blank=True, null=True)
    sentDate = models.DateField()
    dueDate = models.DateField()
    receivedDate = models.DateField(blank=True, null=True)  #to be edited post-creation
    deliveredDate = models.DateField(blank=True, null=True)  #to be edited post-creation
    status = models.CharField(max_length=20, choices=OrderStatusChoices.choices, default=OrderStatusChoices.SENT)
    cost = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=5, blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    #snapshot fields to preserve when foreignkey is deleted (also used for list views)
    labName = models.CharField(max_length=255, blank=True, null=True)
    procedureName = models.CharField(max_length=255, blank=True, null=True)
    patientName = models.CharField(max_length=255, blank=True, null=True)

    #Objects after filtering by manager
    objects = LabOrdersManager()
    
    #to access all objects
    all_objects = models.Manager()


    class Meta:
        db_table = 'LabOrders'
        verbose_name_plural = 'LabOrders'
        ordering = ['branch__name', '-updatedAt']

    def __str__(self):
        return f'[{self.sentDate}] Order for tooth #{self.toothNumber} for patient {self.patient.name}'
    
    @transaction.atomic
    def save(self, *args, **kwargs):
        #Assign dates on creation and updates
        if self._state.adding and not self.sentDate:
            self.sentDate = timezone.localtime(timezone.now()).date 
            self.labName = self.lab.name
            self.procedureName = self.procedure.name
            self.patientName = self.patient.name

        if self.status == self.OrderStatusChoices.RECEIVED:
            self.receivedDate = timezone.localtime(timezone.now()).date
        elif self.status == self.OrderStatusChoices.DELIVERED:
            self.deliveredDate = timezone.localtime(timezone.now()).date
        
        #save changes 
        super().save(*args, **kwargs)


#Sterilization Log Manager 
class SterilizationLogManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
                models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False)
            )

#STERILIZATION LOG MODEL 
class SterilizationLog(models.Model): 
    class CycleTypeChoices(models.TextChoices):
        PRE_VACUUM = 'pre_vacuum', 'Pre-vacuum'
        GRAVITY = 'gravity', 'Gravity'
        FLASH_IMMEDIATE = 'flash_immediate', 'Flash/Immediate'
        CHEMICAL_VAPOR = 'chemical_vapor', 'Chemical Vapor'
        DRY_HEAT = 'dry_heat', 'Dry Heat'
    
    class InstrumentSetsChoices(models.TextChoices):
        BASIC_EXAM_KIT = 'basic_exam_kit', 'Basic Exam Kit'
        EXTRACTION_KIT = 'extraction_kit', 'Extraction Kit'
        RCT_KIT = 'rct_kit', 'RCT Kit'
        IMPLANT_KIT = 'implant_kit', 'Implant Kit'
        PERIO_KIT = 'perio_kit', 'Perio Kit'
        ORTHO_KIT = 'ortho_kit', 'Ortho Kit'
        SURGICAL_KIT = 'surgical_kit', 'Surgical Kit'
        HANDPIECES = 'handpieces', 'Handpieces'
        IMPRESSION_TRAYS = 'impression_trays', 'Impression Trays'
        OTHER = 'other', 'Other'

    class SterilizationResultChoices(models.TextChoices):
        PASSED = 'passed', _('Passed')
        FAILED = 'failed', _('Failed')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(blank=True, null=True)
    time = models.TimeField(blank=True, null=True)
    operator = models.CharField(max_length=255, blank=True, null=True)
    cycleType = models.CharField(max_length=50, choices=CycleTypeChoices.choices)
    instrumentSets = ArrayField(models.CharField(max_length=50, choices=InstrumentSetsChoices.choices), default=list)
    result = models.CharField(max_length=50, choices=SterilizationResultChoices.choices, blank=True, null=True)
    sealedAt = models.DateField(blank=True, null=True)
    shelfLifeDays = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    #Many-to-One relationship to the Branch model (i.e., many logs, one branch)
    branch = models.ForeignKey(Branch, related_name='branch_sterilization_logs', on_delete=models.CASCADE, blank=True, null=True, db_index=True)

    #Objects after filtering by manager
    objects = SterilizationLogManager()
    
    #to access all objects
    all_objects = models.Manager()


    class Meta:
        db_table = 'SterilizationLogs'
        verbose_name_plural = 'SterilizationLogs'
        ordering = ['branch__name', '-updatedAt']

    def __str__(self):
       return f'{self.date} {self.time}: {self.cycleType} -- {self.result}'

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding and not self.date:
            self.date = timezone.localtime(timezone.now()).date
            self.time = timezone.localtime(timezone.now()).time
        
        #if result is 'passed' and no sealed date, set date to today
        if self.result == self.SterilizationResultChoices.PASSED and not self.sealedAt:
            self.sealedAt = timezone.localtime(timezone.now()).date

        #save changes 
        super().save(*args, **kwargs)
