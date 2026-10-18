import uuid 
from decimal import Decimal
from django.utils import timezone
from django.db import models, transaction
from django.contrib.postgres.fields import ArrayField
from patients.validators import validate_phone_number
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy as _context
from django.core.validators import MinValueValidator, MaxValueValidator


#Clinic Tax Configs Manager
class ClinicTaxConfigManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
             models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False)
            )

#CLINIC TAX CONFIG MODEL
class ClinicalTaxConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #tax_config fields
    clinicName = models.CharField(max_length=255)
    taxId = models.CharField(max_length=125, blank=True, null=True)
    activityCode = models.CharField(max_length=125)
    commercialReg = models.CharField(max_length=125)
    address = models.CharField(max_length=500)
    phone = models.CharField(max_length=50, validators=[validate_phone_number])
    #One-to-One relationship to the Branch model (i.e., one tax config, one branch)
    branch = models.OneToOneField('clinic.Branch', related_name='tax_config', blank=True,
                                        null=True, on_delete=models.CASCADE, db_index=True)  #branch should be editable here

    #Objects after filtering by manager
    objects = ClinicTaxConfigManager()
    
    #to access all objects
    all_objects = models.Manager()


    class Meta: 
        db_table = 'ClinicalTaxConfigs'
        verbose_name_plural = 'ClinicalTaxConfigs'
        ordering = ['clinicName']

    def __str__(self):
        return f'{self.clinicName} -- {self.taxId or self.commercialReg}'


#Bills Manager (allows soft deleting)
class BillManager(models.Manager):
    #Overriding get_query to filter out soft-deleted bills
    def get_queryset(self):
        return super().get_queryset().filter(isDeleted=False)

    def earnings(self):
        '''Manager method to retrieve only bills of earnings, excluding deposits and refundable money.'''
        return self.get_queryset().exclude(isDepositBill=True)

    @transaction.atomic 
    def delete_bill(self, user, bill):
        '''
        Custom method to delete bill:
        - Soft-delete for non-admins.
        - Permanent delete for admins.
        '''

        if user.role == 'admin':
            bill.delete()  #delete permenantly
        else:
            #set isDeleted flag to True
            bill.isDeleted = True
            bill.save()
        return True

#BILLS MODEL
class Bill(models.Model):
    class BillStatusChoices(models.TextChoices):
        UNPAID = 'unpaid', _('unpaid')
        PARTIAL = 'partial', _('partial')
        PAID = 'paid', _('paid')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    #Many-to-Many relationship to Visit (one bill, many visits OR many visits, one bill)
    visits = models.ManyToManyField('patients.Visit', related_name='visit_bills', db_index=True)  #NOTE: null doesn't apply on many-to-many relations
    
    #Many-to-One relationships to Patient, TreatmentPlan, Branch (i.e., many bills, one patient/treatment/branch)
    patient = models.ForeignKey('patients.Patient', related_name='patient_bills', on_delete=models.SET_NULL, null=True, db_index=True)
    treatment = models.ForeignKey('patients.TreatmentPlan', related_name='treatment_bills', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    
    #One-to-One relationship to Installment Plan (one bill, one installment plan) -- helps for deletion cascades
    installmentPlan = models.ForeignKey('finances.installmentPlan', related_name='bill', on_delete=models.CASCADE, blank=True, null=True, db_index=True)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_bills', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    
    #bill fields
    description = models.CharField(max_length=300)
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))])
    subtotal = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    totalAmount = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True)
    totalPaid = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    currency = models.CharField(max_length=5, blank=True, null=True)
    #status -- derived -- 'unpaid' | 'partial' | 'paid'
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    #snapshot fields to preserve fields when foreignkey is deleted
    branchName = models.CharField(max_length=255, blank=True, null=True)
    patientName = models.CharField(max_length=255, blank=True, null=True)
    treatmentTitle = models.CharField(max_length=255, blank=True, null=True)
    procedures = ArrayField(models.CharField(max_length=500), default=list, blank=True, null=True)
    createdBy = models.CharField(max_length=255, blank=True, null=True)
    
    #other flags
    isCreditHeld = models.BooleanField(default=False)   #for differentiating credit from paid
    isDepositBill = models.BooleanField(default=False)   #deposit bills only
    isDeleted = models.BooleanField(default=False)   #Soft delete field

    #Objects after filtering by manager
    objects = BillManager()
    
    #to access all objects
    all_objects = models.Manager()

    class Meta: 
        db_table = 'Bills'
        verbose_name_plural = 'Bills'
        ordering = ['branch__name', '-updatedAt']
        #Enforce one-to-one relation between installment plan and undeleted bills
        constraints = [
            models.UniqueConstraint(
                fields=['installmentPlan'],
                condition=models.Q(isDeleted=False),
                name='unique_active_bill_per_treatment_plan'
            )
        ]

    def __str__(self):
        return self.description

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding:
            self.branchName = getattr(self.branch, 'name', None)
            self.patientName = self.patient.name
        if self.treatment:  #only treatment will be updateable
            self.treatmentTitle = getattr(self.treatment, 'title', self.treatmentTitle)
            if self.treatment.treatment_items.exists():
                self.procedures = [
                    item.procedureName for item in self.treatment.treatment_items.all()
                    if item.procedureName
                ]
        
        #adjust overpayments by fractions
        if self.totalPaid and self.totalPaid > self.totalAmount\
         and (self.totalPaid - self.totalAmount) < 1:
            self.totalPaid = self.totalAmount

        #save changes 
        super().save(*args, **kwargs)

    #Model function to auto-generate invoices from a bill
    @classmethod
    def generate_invoice(cls, bill):   
        # #Generate invoice for bill
        invoice, _ = Invoice.objects\
            .update_or_create(
                bill=bill,
                defaults={
                    'patient': bill.patient,
                    'branch': bill.branch,
                    'subtotal': bill.subtotal,
                    'discount': bill.discount,
                    'total': bill.totalAmount,
                    'currency': bill.currency,
                    'status': 'issued',
                }
            )
                
        # if bill.treatment:
        #     treatment_items = bill.treatment.treatment_items.all()
        #     if treatment_items.exists():  #TODO -- this relation better exists between Bill and Invoice (bill items)
        #         invoice_items = []
        #         procedure_ids = treatment_items.values_list('procedure_id', flat=True)
        #         for item in treatment_items.distinct('procedure_id'):
                    
        #             quantity = procedure_ids.count(item.procedure_id)
        #             unitPrice = item.price  #TODO -- this may conflict with procedure price on its respective model
        #             total = quantity*unitPrice
        #             description = getattr(item.procedure, 'name', item.procedureName)

        #             invoice_items.append(
        #                 InvoiceItem(
        #                     invoice=invoice,
        #                     description=description,
        #                     quantity=quantity,
        #                     unitPrice=unitPrice,
        #                     total=total
        #                 )
        #             )
                
        #         #bulk create invoice items 
        #         Invoice.objects.bulk_create(invoice_items)
               
        return invoice


#Transactions Manager 
class TransactionManager(models.Manager):
    #Overriding get_query to filter out soft-deleted transactions
    def get_queryset(self):
        return super().get_queryset().filter(isDeleted=False)

    def completed(self):
        '''Manager method to retrieve only completed transactions representing real, current money — excludes refunds.'''
        return self.get_queryset().exclude(status='refunded')

    @transaction.atomic 
    def delete_transaction(self, user, transaction):
        '''
        Custom method to delete transaction:
        - Soft-delete for non-admins.
        - Permanent delete for admins.
        '''

        if user.role == 'admin':
            transaction.delete()  #delete permenantly
        else:
            #set isDeleted flag to True
            transaction.isDeleted = True
            transaction.save()
        return True

#TRANSACTIONS MODEL
class Transaction(models.Model):
    class PaymentMethodChoices(models.TextChoices):
        CASH = 'cash', _('Cash')
        CARD = 'card', _('Card')
        BANK_TRANSFER = 'bank_transfer', _('Bank transfer')
        INSURANCE = 'insurance', _('Insurance')
        MOBILE_WALLET = 'mobile_wallet', _('Mobile wallet')

    class TransactionTypeChoices(models.TextChoices):
        TREATMENT_PAYMENT = 'treatment_payment', _('Treatment payment')
        INSTALLMENT = 'installment', _('Installment')
        VISIT_FEE = 'visit_fee', _('Visit fee')
        DEPOSIT = 'deposit', _('Deposit')
        OTHER = 'other', _context('transaction_type', 'Other')
    
    class TransactionStatusChoices(models.TextChoices):
        PENDING_CORRECTION = 'pending_correction', _('Pending correction')
        REFUNDED = 'refunded', _('Refunded')
        COMPLETED = 'completed', _('Completed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationships to Bill, Patient, Visit, & Branch (i.e., many transactions, one bill/patient/visit/branch)
    bill = models.ForeignKey(Bill, related_name='transactions', on_delete=models.SET_NULL, null=True, db_index=True)
    patient = models.ForeignKey('patients.Patient', related_name='patient_transactions', on_delete=models.SET_NULL, null=True, db_index=True)
    visit = models.ForeignKey('patients.Visit', related_name='visit_transactions', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_transactions', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    
    #transaction fields
    date = models.DateField()
    amount = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    currency = models.CharField(max_length=5, blank=True, null=True)
    method = models.CharField(max_length=25, choices=PaymentMethodChoices.choices, blank=True, null=True)
    status = models.CharField(max_length=20, choices=TransactionStatusChoices.choices, blank=True, null=True)
    type = models.CharField(max_length=50, choices=TransactionTypeChoices.choices, blank=True, null=True)
    notes = models.CharField(max_length=500, blank=True, null=True)
    updatedAt = models.DateTimeField(auto_now=True)
    
    #fields for refunds and corrections
    refundReason = models.CharField(max_length=500, blank=True, null=True)
    correctionReason = models.CharField(max_length=500, blank=True, null=True)
    #treatment id -- for treatment deposits
    treatmentId = models.UUIDField(blank=True, null=True)  

    #snapshot fields to preserve fields when foreignkey is deleted (also will be shown to admin only)
    patientName = models.CharField(max_length=255, blank=True, null=True)
    billDescription = models.CharField(max_length=300, blank=True, null=True)
    branchName = models.CharField(max_length=255, blank=True, null=True)
    treatmentTitle = models.CharField(max_length=255, blank=True, null=True)
    createdBy = models.CharField(max_length=255, blank=True, null=True)
    isDeleted = models.BooleanField(default=False)   #Soft delete field

    #Objects after filtering by manager
    objects = TransactionManager()
    
    #to access all objects
    all_objects = models.Manager()

    class Meta: 
        db_table = 'Transactions'
        verbose_name_plural = 'Transactions'
        ordering = ['branch__name', '-date', 'patient__name']

    def __str__(self):
        return f'[{self.date}] {self.method} transaction -- {self.billDescription}'

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding:
            #automatically assign status as completed on creation
            self.status = 'completed'

            if not self.method:
                self.method = 'cash'
            
            #auto--fill snashot fields
            self.billDescription = getattr(self.bill, 'description', None)
            self.branchName = getattr(self.branch, 'name', None)
            self.patientName = getattr(self.patient, 'name', None)
            self.treatmentTitle = getattr(self.bill, 'treatmentTitle', None) or self.treatmentTitle

            #determine transaction type
            if not self.type:
                if self.visit and not getattr(self.bill, 'treatment', None):
                    self.type = 'visit_fee'
                elif getattr(self.bill, 'treatment', None):
                    self.type = 'treatment_payment'
                else:
                    self.type = 'other'   #for BillId only
                        
        #update refund reason on refunds
        if self.refundReason and self.status != 'refunded':
            self.refundReason = None

        #update correction reason on corrections
        if self.correctionReason and self.status != 'pending_correction':
            self.correctionReason = None
                
        #save changes 
        super().save(*args, **kwargs)
    
    @classmethod
    def autogenerate_deposit_after_reducing_costs_below_paid(cls, amount, treatment, plan=None):
        #prepare necessary details
        patient = treatment.patient 
        amount = Decimal(str(abs(amount)))  #always use positive cost
        currency = (getattr(plan, 'currency', None) or treatment.currency)
        date_today = timezone.localdate(timezone.now())

        #Create settled bill to show in the payment records
        bill = Bill.objects.create(   #TODO - until frontend resolves this
            patient=patient,
            treatment_id=treatment.id,
            branch=(patient.branch or getattr(plan, 'branch', None)),
            subtotal=amount,
            totalAmount=amount,
            totalPaid=amount,
            currency=currency,
            isCreditHeld=True,
            isDepositBill=True,
            description=("This bill was autogenerated after a treatment plan cost was lowered "
                         "below what the patient has already paid to keep a record of the money "
                         "withheld to be returned to the patient.")
        )

        deposit = cls.objects.create(
            patient=patient,
            bill=bill,
            treatmentId=treatment.id,
            branch=(patient.branch or getattr(plan, 'branch', None)),
            date=date_today,
            method='cash',
            currency=currency,
            amount=amount,
            type='deposit',
            status='completed',
            notes=("This transaction record was autogenerated after treatment plan cost was lowered "
                   "below what the patient has already paid and treated as withheld money to be returned "
                   "to the patient.")
        )

        return deposit


#Installment Plans Manager
class InstallmentPlansManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(treatment__patient__is_deleted=False)

#INSTALLMENT PLAN MODEL 
class InstallmentPlan(models.Model):
    class InstallmentMonthsChoices(models.IntegerChoices):
        FULL_PAYMENT = 1, _('Full payment')
        THREE_MONTHS = 3, _('3 months')
        SIX_MONTHS = 6, _('6 months')
        TWELVE_MONTHS = 12, _('12 months')

    class InstallmentPlanStatusChoices(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PARTIAL = 'partial', _('Partial')
        COMPLETED = 'completed', _('Completed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #One-to-One relationship to TreatmentPlan (i.e., one treatment plan, one installment plan)
    treatment = models.OneToOneField('patients.TreatmentPlan', related_name='installment_plan', on_delete=models.CASCADE, db_index=True)
    #Many-to-One relationships to Bill, Patient, Visit, Treatment, & Branch (i.e., many transactions, one bill/patient/visit/treatment/branch)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_installments', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)  #derived from patient
    installmentMonths = models.PositiveSmallIntegerField(choices=InstallmentMonthsChoices.choices)
    totalAmount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(Decimal('0'))])
    totalPaid = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'), blank=True, null=True, validators=[MinValueValidator(Decimal('0'))])
    currency = models.CharField(max_length=5, blank=True, null=True)
    # status -- derived -- pending | partial | completed
    startDate = models.DateField()
    downPayment = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))])
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    #Objects after filtering by manager
    objects = InstallmentPlansManager()

    #to access all objects
    all_objects = models.Manager()
    
    class Meta:
        db_table = 'InstallmentPlans'
        verbose_name_plural = 'InstallmentPlans'
        ordering = ['-updatedAt']

    @property
    def active_bill(self): 
        return self.bill.filter(isDeleted=False).first()

    # def __str__(self):
    #     return f'Installment plan for {self.treatment.patient.name} ({self.installmentMonths} months)'

    @transaction.atomic
    def save(self, *args, **kwargs):
        #adjust overpayments by fractions
        if self.totalPaid and self.totalPaid > self.totalAmount\
         and (self.totalPaid - self.totalAmount) < 1:
            self.totalPaid = self.totalAmount

        #save changes 
        super().save(*args, **kwargs)


#Installments Manager
class InstallmentsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(installmentPlan__treatment__patient__is_deleted=False)

#INSTALLMENTS MODEL
class Installment(models.Model):
    class InstallmentTypeChoices(models.TextChoices):
        DOWN_PAYMENT = 'down_payment', _('Down payment')
        INSTALLMENT = 'installment', _('Installment')
    
    class InstallmentStatusChoices(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAID = 'paid', _('Paid')
        OVERDUE = 'overdue', _('Overdue')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #Many-to-One relationship to InstallmentPlan & Transaction (i.e., many installments, one plan, one transaction)
    installmentPlan = models.ForeignKey(InstallmentPlan, related_name='installments', on_delete=models.CASCADE, db_index=True)
    transaction = models.ForeignKey(Transaction, related_name='installments', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)

    #core fields
    amount = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    sequence = models.IntegerField()   #0 = down payment, 1..N = installments
    dueDate = models.DateField()
    type = models.CharField(max_length=25, choices=InstallmentTypeChoices.choices)
    #status -- derived -- pending | paid | overdue
    paidAt = models.DateTimeField(null=True, blank=True)

    #Objects after filtering by manager
    objects = InstallmentsManager()

    #to access all objects
    all_objects = models.Manager()

    class Meta:
        db_table = 'Installments'
        verbose_name_plural = 'Installments'
        ordering = ['installmentPlan', 'sequence']
        constraints = [
            models.UniqueConstraint(fields=['installmentPlan', 'sequence'], name='unique_installment_sequence')
        ]

    def __str__(self):
        return f'Installment #{self.sequence} of plan #{self.installmentPlan_id} (due {self.dueDate})'


#Invoices Manager
class InvoiceManager(models.Manager):
    #Overriding get_query to filter out soft-deleted invoices
    def get_queryset(self):
        return super().get_queryset().filter(isDeleted=False)

    @transaction.atomic 
    def delete_invoice(self, user, invoice):
        '''
        Custom method to delete invoice:
        - Soft-delete for non-admins.
        - Permanent delete for admins.
        '''

        if user.role == 'admin':
            invoice.delete()  #delete permenantly
        else:
            #set isDeleted flag to True
            invoice.isDeleted = True
            invoice.save()
        return True

#INVOICES MODEL
class Invoice(models.Model):
    class InvoiceStatusChoices(models.TextChoices):
        ISSUED = 'issued', _('Issued')
        SUBMITTED = 'submitted', _('Submitted')
        ACCEPTED = 'accepted', _('Accepted')
        REJECTED = 'rejected', _('Rejected')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #One-One relationship to Bill for auto-generated invoices
    bill = models.OneToOneField(Bill, related_name='bill_invoice', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    #Many-to-One relationships to Patient, Branch (i.e., many invoices, one patient/branch)
    patient = models.ForeignKey('patients.Patient', related_name='patient_invoices', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_invoices', on_delete=models.SET_NULL, blank=True, null=True, db_index=True)
    
    #money fields
    subtotal = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    tax = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))])
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))])
    total = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    currency = models.CharField(max_length=5, blank=True, null=True)
    
    #invoice state fields
    invoiceNumber = models.CharField(max_length=250, null=True, blank=True)
    status = models.CharField(max_length=10, choices=InvoiceStatusChoices.choices, db_index=True)
    issuedAt = models.DateTimeField(blank=True, null=True)
    submittedAt = models.DateTimeField(blank=True, null=True)

    #recipient details for a custom (non-patient) invoice
    billedToName = models.CharField(max_length=255, blank=True, null=True)
    billedToTaxId = models.CharField(max_length=100, blank=True, null=True)
    billedToAddress = models.CharField(max_length=500, blank=True, null=True)

    #snapshot fields to preserve fields when foreignkey is deleted (also will be shown to admin only)
    billDescription = models.CharField(max_length=300, blank=True, null=True)
    patientName = models.CharField(max_length=255, blank=True, null=True)
    patientNationalId = models.CharField(max_length=120, blank=True, null=True)
    branchName = models.CharField(max_length=255, blank=True, null=True)
    treatmentTitle = models.CharField(max_length=255, blank=True, null=True)
    createdBy = models.CharField(max_length=255, blank=True, null=True)

    #backend fields
    createdAt = models.DateTimeField(auto_now_add=True)
    isDeleted = models.BooleanField(default=False)   #Soft delete field
    
    #Objects after filtering by manager
    objects = InvoiceManager()
    
    #to access all objects
    all_objects = models.Manager()


    class Meta: 
        db_table = 'Invoices'
        verbose_name_plural = 'Invoices'
        ordering = ['branch__name', '-issuedAt', '-submittedAt', 'patient__name']

    def __str__(self):
        return self.invoiceNumber

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding:
            #fixed fields upon creation
            this_year = timezone.localtime(timezone.now()).year
            self.invoiceNumber = f'INV-{str(this_year)}-{str(Invoice.objects\
                                                             .only('id','createdAt','branch')\
                                                             .filter(createdAt__year=this_year,branch=self.branch)\
                                                            .count()+1).zfill(5)}'
            self.branchName = getattr(self.branch, 'name', None)
            self.patientName = getattr(self.patient, 'name', None)
            self.patientNationalId = getattr(self.patient, 'nationalId', None)
        
        #snapshot fields that can change with updates
        if self.bill:
            self.billDescription = getattr(self.bill, 'description', None) or self.billDescription
            self.treatmentTitle = getattr(self.bill, 'treatmentTitle', None) or self.treatmentTitle
        
        #update dates based on status
        if self.status == 'issued' and not self.issuedAt:
            self.issuedAt = timezone.localtime(timezone.now())
            # self.submittedAt = timezone.localtime(timezone.now())

        elif self.status == 'submitted':
            self.submittedAt = timezone.localtime(timezone.now())

        super().save(*args, **kwargs)

#INVOICE ITEMS MODEL
class InvoiceItem(models.Model):
    class TaxCodeChoices(models.TextChoices):
        D0120 = 'D0120', 'D0120'
        D0210 = 'D0210', 'D0210'
        D0330 = 'D0330', 'D0330'
        D1110 = 'D1110', 'D1110'
        D1120 = 'D1120', 'D1120'
        D2140 = 'D2140', 'D2140'
        D2390 = 'D2390', 'D2390'
        D2710 = 'D2710', 'D2710'
        D2750 = 'D2750', 'D2750'
        D2780 = 'D2780', 'D2780'
        D3310 = 'D3310', 'D3310'
        D3330 = 'D3330', 'D3330'
        D4341 = 'D4341', 'D4341'
        D5110 = 'D5110', 'D5110'
        D5120 = 'D5120', 'D5120'
        D6010 = 'D6010', 'D6010'
        D6065 = 'D6065', 'D6065'
        D7140 = 'D7140', 'D7140'
        D7210 = 'D7210', 'D7210'
        D8080 = 'D8080', 'D8080'
        D9930 = 'D9930', 'D9930'
        OTHER = 'other', 'Other'

    #Many-to-One relationship to the Invoice model (i.e., many invoice items, one invoice)
    invoice = models.ForeignKey(Invoice, related_name='invoice_items', on_delete=models.CASCADE)
    taxCode = models.CharField(max_length=10, choices=TaxCodeChoices.choices, blank=True, null=True)
    description = models.CharField(max_length=300, blank=True, null=True)  #OR, bill description!
    quantity = models.SmallIntegerField(blank=True, null=True, default=1)
    unitPrice = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    total = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    
    class Meta:
        db_table = 'InvoiceItems'
        verbose_name_plural = 'InvoiceItems'


#Insurance Provider Manager
class InsuranceProviderManager(models.Manager):
    #Overriding get_query to filter out soft-deleted branches
    def get_queryset(self): 
        return super().get_queryset().filter(
             models.Q(branch__isnull=True) | models.Q(branch__is_deleted=False)
            )

#INSURANCE PROVIDER MODEL 
class InsuranceProvider(models.Model):
    class InuranceTierChoices(models.TextChoices):
        GOVERNMENT = 'government', _('Government')
        UNIVERSAL = 'universal', _('Universal')
        CORPORATE = 'corporate', _('Corporate')
        DIRECT = 'direct', _('Direct')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    fullName = models.CharField(max_length=300, blank=True, null=True)
    region = models.CharField(max_length=120, blank=True, null=True)
    tier = models.CharField(max_length=25, choices=InuranceTierChoices.choices)
    contact = models.CharField(max_length=150, blank=True, null=True)
    coveragePercent = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    annualMax = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    deductible = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))], blank=True, null=True)
    currency = models.CharField(max_length=5, blank=True, null=True)
    responseDays = models.PositiveIntegerField(blank=True, null=True)
    color = models.CharField(max_length=10, blank=True, null=True)  #hex
    notes = models.TextField(blank=True, null=True)
    
    #Many-to-One relationships to Branch (i.e., many providers, one branch)
    branch = models.ForeignKey('clinic.Branch', related_name='branch_providers', 
                  on_delete=models.CASCADE, blank=True, null=True, db_index=True)


    #Objects after filtering by manager
    objects = InsuranceProviderManager()
    
    #to access all objects
    all_objects = models.Manager()


    class Meta: 
        db_table = 'InsuranceProviders'
        verbose_name_plural = 'InsuranceProviders'
        unique_together = ['name', 'branch']
        ordering = ['branch__name', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.fullName:
            self.fullName = self.name 

        if not self.deductible:
            self.deductible = self.deductible if (self.coveragePercent != 100) else Decimal('0')

        super().save(*args, **kwargs)

