import json
import uuid 
from django.db import models
from django.db import transaction
from clinic.models import WorkingDaysLookUp
from users.validators import validate_image_size
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


#Define user manager 
class UserManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)  #filter out soft-deleted users
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        #normalize email (i.e., lowercase, etc.)
        email = self.normalize_full_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)        
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)
    
    @staticmethod
    def normalize_full_email(email):
        return (email or '').strip().lower()

    def get_by_natural_key(self, username):
        '''Makes login case-insensitive.'''
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': self.normalize_full_email(username)})

    @transaction.atomic
    def delete_user(self, user):
        '''Custom method to soft-delete users.'''
        from patients.models import Patient, Appointment
        user.is_deleted = True
        user.save(update_fields=['is_deleted'])
        #Handle related models if user is Dentist
        if user.role == 'dentist':
            Patient.all_objects.filter(doctor_id=user.id).update(doctor=None)
            Appointment.objects.filter(
                doctor_id=user.id, status__in=['pending', 'confirmed']
                ).update(doctor=None)
        return True

    
    @transaction.atomic
    def delete_user_permanently(self, user_id):
        try:
            user = self.model.all_objects.get(id=user_id)
            user.delete()
            return True 
        except self.model.DoesNotExist:
            return False 

#USERS MODEL 
class User(AbstractBaseUser, PermissionsMixin):
    class UserRoles(models.TextChoices):
        ADMIN = 'admin', _('Admin')
        DENTIST = 'dentist', _('Dentist')
        RECEPTIONIST = 'receptionist', _('Receptionist')
        ASSISTANT = 'assistant', _('Assistant')
        ACCOUNTANT = 'accountant', _('Accountant')

    #User account fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, db_index=True)
    role = models.CharField(max_length=15, choices=UserRoles.choices)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    avatar = models.ImageField(upload_to='user_avatars/', blank=True, null=True, validators=[validate_image_size])
    userPermissions = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    #Many-to-One relationship to the Branch model (i.e., many users, one branch)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_users', blank=True,
                                null=True, on_delete=models.SET_NULL, db_index=True)
    #other fields 
    isActive = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    createdAt = models.DateField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  #Soft-delete field


    USERNAME_FIELD = 'email'

    #fields for superusers 
    REQUIRED_FIELDS = ['name', 'role'] 

    #Objects after filtering by manager
    objects = UserManager()

    #to access all objects
    all_objects = models.Manager()


    #Dictionary breaking down permissions by category 
    USER_PERMISSIONS_DICT = {
        #Users permissions
        # 'users': (
        #     'create.user',  #admin only
        #     'view.users',   #admin only
        #     'view.userDetail',  #user/owner only (by default)
        #     'update.user',  #user and admin (but not for role & permissions)
        #     'delete.user',  #admin only 
        # ), 

        # #Branch permissions -- admin only
        # 'users': (
        #     'create.branch',  
        #     'view.branches',
        #     'view.branchDetail',  
        #     'update.branch', 
        #     'delete.branch',  
        # ), 

        #Patients permissions
        'patients': (
            'view.patients',
            'view.patientDetail',  #extends to dental chart
            'create.patient',
            'update.patient',    #extends to dental chart 
            'delete.patient'
        ),


        #Patient visit history permissions
        'visits': (
            'view.visits',
            'create.visit'
        ),

        #Appointments permissions 
        'appointments': (
            'view.appointments',
            'view.appointmentDetail',
            'create.appointment',
            'update.appointment',
            'delete.appointment',
            'send.whatsappMessage'
        ),

        #Treatment plans permissions
        'treatment-plans': (
            'view.treatments',
            'create.treatment',
            'update.treatment',
            'delete.treatment'
        ),

        #Procedures permission
        'procedures': (
            'view.procedures',
            'create.procedure',
            'update.procedure',
            'delete.procedure',
        ),

        #Inventory permissions
        'inventory': (
            'view.inventory',
            'create.inventory',
            'update.inventory',
            'delete.inventory'
        ),

        #Doctor schedules permissions
        'doctor-schedules': (
            'view.doctorSchedules',
            'view.doctorScheduleDetial',
            'create.doctorSchedule',
            'update.doctorSchedule',
            'delete.doctorSchedule',
        ),

        #Labs permissions
        'labs': (
            'view.labs',
            'create.lab',
            'update.lab',
            'delete.lab',
        ),

        #Lab orders permissions 
        'lab-orders': (
            'view.labOrders',
            'view.labOrderDetail',
            'create.labOrder',
            'update.labOrder',
            'delete.labOrder',
        ),

        #Sterilization logs permissions 
        'sterilization-logs': (
            'view.sterilizationLogs',
            'create.sterilizationLog',
            'update.sterilizationLog',
            'delete.sterilizationLog'
        ),

        'patient-recalls': (
            'view.recalls',
            'create.recall',
            'update.recall',
            'delete.recall'
        ),

        #Default sidebar permissions 
        'sidebar': (
            'view.patients',
            'view.appointments',
            'view.procedures',
            'view.inventory',
            # 'view.doctorSchedules'
            'view.labs',
            'view.labOrders',
            'view.sterilizationLogs'
            'view.recalls',
        )

    }

    #User permissions tuple -- extract permission name only 
    USER_PERMISSIONS = tuple(
        perm for category, permissions in USER_PERMISSIONS_DICT.items() 
        if category != 'sidebar'
        for perm in permissions
    )

    #Default permissions for each role
    DEFAULT_ROLE_PERMISSIONS = {
        'admin': list(USER_PERMISSIONS),  #Admin gets all permissions
        
        'dentist': [
            perm for perm in USER_PERMISSIONS 
            if perm not in ('delete.patient', 'send.whatsappMessage')
        ], 

        #NOTE - view.patientDetail extends to detal-chart detail view
        #     - update.patient extends to dental-chart update view

        'receptionist': [
            'view.patients', 'create.patient', 'update.patient', 'view.appointments', 
            'view.appointmentDetail', 'create.appointment', 'update.appointment', 
            'delete.appointment', 'view.recalls', 'create.recall', 'update.recall',
            'delete.recall', 'send.whatsappMessage'
        ],
        
        'assistant': [  
            'view.inventory', 'create.inventory', 'update.inventory', 'delete.inventory',
            'view.labs', 'view.labOrders', 'view.labOrderDetail', 'create.labOrder', 'update.labOrder',
            'view.sterilizationLogs', 'create.sterilizationLog', 'update.sterilizationLog',
        ], 

        'accountant': []  #TODO - to be defined later
    }


    #Has reverse relations to four core models
    #Accessible via:
     # doctor.doctor_patients.all() for related_name='doctor_patients' on Patient
     # doctor.doctor_visits.all() for related_name='doctor_visits' on Visit
     # doctor.doctor_appointments.all() for related_name='doctor_appointments' on Appointment
     # doctor.doctor_treatmentplans.all() for related_name='doctor_treatmentplans' on TreatmentPlan
     # doctor.doctor_schedule for related_name='doctor_schedule' on DoctorSchedule


    class Meta:
        db_table = 'Users'
        verbose_name_plural = 'Users'
        ordering = ['name']

    def __str__(self):
        return self.name

    @transaction.atomic 
    def save(self, *args, **kwargs):
        #Normalize email before saving 
        if self.email:
            self.email = self.email.strip().lower()

        #Set default permissions based on role if userPermissions is empty
        if self._state.adding and not self.userPermissions and self.role:
            self.userPermissions = self.DEFAULT_ROLE_PERMISSIONS.get(self.role, [])

        elif self.userPermissions:
            if isinstance(self.userPermissions, dict):
                self.userPermissions = [perm for perm, val in self.userPermissions.items() if val]
            elif not isinstance(self.userPermissions, list):
                try:
                    self.userPermissions = list(json.loads(self.userPermissions))
                except (json.JSONDecodeError, TypeError):
                    self.userPermissions = self.format_array(self.userPermissions)

        super().save(*args, **kwargs)

    @staticmethod
    def format_array(array):
        if not array:
            return '{}'
        array = [f'"{val}"' for val in array]  
        return '{' + ','.join(array) + '}'
    
    def has_special_permission(self, permission):
        '''
        Checks if user has a specific custom permission. 
        **Note: Named 'has_special_permission' to avoid Django built-in function, has_permission.
        '''

        if self.role == 'admin':
            return True
        return permission in self.userPermissions  #boolean True or False 

    def get_user_permissions(self, perm_category=None):
        '''Get user permissions (by category) for API responses.'''
       
        if not perm_category:
            perm_category = 'sidebar'
        available_permissions = list(self.USER_PERMISSIONS_DICT['sidebar']) + list(self.USER_PERMISSIONS_DICT[perm_category])
        available_permissions = list(dict.fromkeys(available_permissions))
        return {permission: permission in self.userPermissions 
                for permission in available_permissions
            }
    

#Doctor Schedule Manager
class DoctorSchedulesManager(models.Manager):
    #Overriding get_query to filter out soft-deleted users
    def get_queryset(self): 
        return super().get_queryset().filter(doctor__is_deleted=False)

#DOCTOR SCHEDULE MODEL
class DoctorSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #One-to-One relationships to the User model -- reserved for doctors
    doctor = models.OneToOneField(User, related_name='doctor_schedule', on_delete=models.CASCADE)
    workingDays = ArrayField(models.IntegerField(choices=WorkingDaysLookUp.choices), default=list)
    startTime = models.TimeField()
    endTime = models.TimeField()
    breakStart = models.TimeField(blank=True, null=True)
    breakEnd = models.TimeField(blank=True, null=True)

    #Objects after filtering by manager
    objects = DoctorSchedulesManager()

    #to access all objects
    all_objects = models.Manager()

    #Has a reverse relation to the DoctorScheduleException model:
     # schedule.exceptions.all() for related_name='exceptions' on DoctorScheduleException

    class Meta:
        db_table = 'DoctorSchedules'
        verbose_name_plural = 'DoctorSchedules'
        ordering = ['doctor__name', '-startTime']

    def __str__(self):
        return f'{self.doctor.name}\'s Schedule'


#Doctor Schedule Exceptions Manager
class DoctorScheduleExceptionsManager(models.Manager):
    #Overriding get_query to filter out soft-deleted users
    def get_queryset(self): 
        return super().get_queryset().filter(schedule__doctor__is_deleted=False)

#EXCEPTIONS MODEL -- supplements DoctorSchedule model
class DoctorScheduleException(models.Model):
    class ExceptionTypeChoices(models.TextChoices):
        OFF = 'off', _('Off')
        VACATION = 'vacation', _('Vacation')
        CONFERENCE = 'conference', _('Conference')

    #Many-to-One relationship to the DoctorSchedule model (i.e., many exceptions, one schedule)
    schedule = models.ForeignKey(DoctorSchedule, related_name='exceptions', on_delete=models.CASCADE)
    #other fields
    date = models.DateField()
    type = models.CharField(max_length=20, choices=ExceptionTypeChoices.choices)
    note = models.CharField(max_length=255, blank=True, null=True)

    #Objects after filtering by manager
    objects = DoctorScheduleExceptionsManager()

    #to access all objects
    all_objects = models.Manager()


    class Meta:
        db_table = 'DoctorScheduleExceptions'
        verbose_name_plural = 'DoctorScheduleExceptions'
    
    def __str__(self):
        return f'[{self.date}] {self.type}'

