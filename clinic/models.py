from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Department(TimeStamped):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    floor = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Doctor(TimeStamped):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='doctor_profile')
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='doctors')
    specialization = models.CharField(max_length=100)
    qualification = models.CharField(max_length=150, blank=True)
    license_no = models.CharField(max_length=30, unique=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('500.00'))
    available_days = models.CharField(max_length=60, default='Sun,Mon,Tue,Wed,Thu',
                                      help_text='Comma separated, e.g. Sun,Mon,Tue')
    shift_start = models.TimeField(default='09:00')
    shift_end = models.TimeField(default='17:00')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'Dr. {self.first_name} {self.last_name}'

    @property
    def full_name(self):
        return f'Dr. {self.first_name} {self.last_name}'

    def get_absolute_url(self):
        return reverse('doctor_detail', args=[self.pk])


class Patient(TimeStamped):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    BLOOD_GROUPS = [(g, g) for g in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']]

    mrn = models.CharField('MRN', max_length=20, unique=True, editable=False)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUPS, blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    insurance_provider = models.CharField(max_length=100, blank=True)
    insurance_number = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['last_name', 'first_name']), models.Index(fields=['phone'])]

    def save(self, *args, **kwargs):
        if not self.mrn:
            n = (Patient.objects.order_by('-id').values_list('id', flat=True).first() or 0) + 1
            while Patient.objects.filter(mrn=f'MRN{n:06d}').exists():
                n += 1
            self.mrn = f'MRN{n:06d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.mrn})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def age(self):
        today = timezone.localdate()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def get_absolute_url(self):
        return reverse('patient_detail', args=[self.pk])


class Appointment(TimeStamped):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        CHECKED_IN = 'checked_in', 'Checked in'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        NO_SHOW = 'no_show', 'No show'

    class VisitType(models.TextChoices):
        NEW = 'new', 'New visit'
        FOLLOW_UP = 'follow_up', 'Follow-up'
        EMERGENCY = 'emergency', 'Emergency'

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='appointments')
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=15)
    visit_type = models.CharField(max_length=20, choices=VisitType.choices, default=VisitType.NEW)
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-scheduled_at']
        indexes = [models.Index(fields=['scheduled_at']), models.Index(fields=['status'])]

    def __str__(self):
        return f'{self.patient.full_name} with {self.doctor} on {timezone.localtime(self.scheduled_at):%Y-%m-%d %H:%M}'

    def get_absolute_url(self):
        return reverse('appointment_detail', args=[self.pk])

    @property
    def status_badge(self):
        return {
            'scheduled': 'primary', 'checked_in': 'info', 'completed': 'success',
            'cancelled': 'secondary', 'no_show': 'warning',
        }.get(self.status, 'light')


class Consultation(TimeStamped):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='consultation')
    chief_complaint = models.CharField(max_length=255)
    symptoms = models.TextField(blank=True)
    diagnosis = models.CharField(max_length=255)
    icd10_code = models.CharField('ICD-10 code', max_length=10, blank=True)
    notes = models.TextField(blank=True)
    # vitals
    blood_pressure = models.CharField(max_length=10, blank=True, help_text='e.g. 120/80')
    pulse = models.PositiveIntegerField(null=True, blank=True, help_text='bpm')
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text='°F')
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    spo2 = models.PositiveIntegerField('SpO₂ (%)', null=True, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Consultation: {self.appointment}'

    @property
    def patient(self):
        return self.appointment.patient

    @property
    def doctor(self):
        return self.appointment.doctor

    @property
    def bmi(self):
        if self.weight_kg and self.height_cm:
            h = float(self.height_cm) / 100
            return round(float(self.weight_kg) / (h * h), 1)
        return None


class Medicine(TimeStamped):
    FORMS = [(f, f) for f in ['Tablet', 'Capsule', 'Syrup', 'Injection', 'Ointment', 'Drops', 'Inhaler']]

    name = models.CharField(max_length=120)
    generic_name = models.CharField(max_length=120)
    form = models.CharField(max_length=20, choices=FORMS)
    strength = models.CharField(max_length=40)
    manufacturer = models.CharField(max_length=120, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=50)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('name', 'strength', 'form')]

    def __str__(self):
        return f'{self.name} {self.strength} ({self.form})'

    @property
    def low_stock(self):
        return self.stock_quantity <= self.reorder_level


class Prescription(TimeStamped):
    consultation = models.OneToOneField(Consultation, on_delete=models.CASCADE, related_name='prescription')
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f'Rx #{self.pk} for {self.consultation.patient.full_name}'


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT, related_name='prescription_items')
    dosage = models.CharField(max_length=60, help_text='e.g. 1 tablet')
    frequency = models.CharField(max_length=60, help_text='e.g. 1+0+1')
    duration_days = models.PositiveIntegerField(default=7)
    quantity = models.PositiveIntegerField(default=1)
    instructions = models.CharField(max_length=120, blank=True, help_text='e.g. after meal')

    def __str__(self):
        return f'{self.medicine} - {self.dosage} {self.frequency} x {self.duration_days}d'


class LabTest(TimeStamped):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    normal_range = models.CharField(max_length=120, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    turnaround_hours = models.PositiveIntegerField(default=24)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class LabOrder(TimeStamped):
    class Status(models.TextChoices):
        ORDERED = 'ordered', 'Ordered'
        SAMPLE_COLLECTED = 'collected', 'Sample collected'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_orders')
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='lab_orders')
    ordered_by = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_orders')
    test = models.ForeignKey(LabTest, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ORDERED)
    result_value = models.CharField(max_length=120, blank=True)
    result_notes = models.TextField(blank=True)
    is_abnormal = models.BooleanField(default=False)
    ordered_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-ordered_at']
        indexes = [models.Index(fields=['status'])]

    def __str__(self):
        return f'{self.test.name} for {self.patient.full_name}'

    @property
    def status_badge(self):
        return {'ordered': 'primary', 'collected': 'info', 'completed': 'success',
                'cancelled': 'secondary'}.get(self.status, 'light')


class Invoice(TimeStamped):
    class Status(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PARTIAL = 'partial', 'Partially paid'
        PAID = 'paid', 'Paid'
        VOID = 'void', 'Void'

    invoice_no = models.CharField(max_length=20, unique=True, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='invoices')
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='invoices')
    issued_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField(null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_on', '-id']

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            n = (Invoice.objects.order_by('-id').values_list('id', flat=True).first() or 0) + 1
            while Invoice.objects.filter(invoice_no=f'INV{n:07d}').exists():
                n += 1
            self.invoice_no = f'INV{n:07d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_no

    def get_absolute_url(self):
        return reverse('invoice_detail', args=[self.pk])

    @property
    def subtotal(self):
        return sum((i.line_total for i in self.items.all()), Decimal('0'))

    @property
    def total(self):
        return max(self.subtotal - self.discount, Decimal('0'))

    @property
    def amount_paid(self):
        # iterate (instead of aggregate) so prefetch_related('payments') is honoured
        return sum((p.amount for p in self.payments.all()), Decimal('0'))

    @property
    def balance(self):
        return self.total - self.amount_paid

    def refresh_status(self, save=True):
        if self.status == self.Status.VOID:
            return
        paid = self.amount_paid
        if paid <= 0:
            self.status = self.Status.UNPAID
        elif paid < self.total:
            self.status = self.Status.PARTIAL
        else:
            self.status = self.Status.PAID
        if save:
            self.save(update_fields=['status', 'updated_at'])

    @property
    def status_badge(self):
        return {'unpaid': 'danger', 'partial': 'warning', 'paid': 'success', 'void': 'secondary'}.get(self.status)


class InvoiceItem(models.Model):
    class Kind(models.TextChoices):
        CONSULTATION = 'consultation', 'Consultation'
        LAB = 'lab', 'Lab test'
        MEDICINE = 'medicine', 'Medicine'
        PROCEDURE = 'procedure', 'Procedure'
        OTHER = 'other', 'Other'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTHER)
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.description

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Payment(TimeStamped):
    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card'
        MOBILE = 'mobile', 'Mobile banking'
        INSURANCE = 'insurance', 'Insurance'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=60, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f'{self.amount} via {self.get_method_display()} for {self.invoice}'
