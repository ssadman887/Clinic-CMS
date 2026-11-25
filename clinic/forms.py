from django import forms
from django.forms import inlineformset_factory

from .models import (Appointment, Consultation, Doctor, Invoice, InvoiceItem, LabOrder, LabTest, Medicine,
                     Patient, Payment, Prescription, PrescriptionItem)


class BootstrapMixin:
    """Adds Bootstrap classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault('class', 'form-select')
            else:
                w.attrs.setdefault('class', 'form-control')
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault('rows', 3)


class DateInput(forms.DateInput):
    input_type = 'date'


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def __init__(self, **kwargs):
        kwargs.setdefault('format', '%Y-%m-%dT%H:%M')
        super().__init__(**kwargs)


class TimeInput(forms.TimeInput):
    input_type = 'time'


class PatientForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Patient
        exclude = ['mrn']
        widgets = {'date_of_birth': DateInput()}


class DoctorForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Doctor
        exclude = ['user']
        widgets = {'shift_start': TimeInput(), 'shift_end': TimeInput()}


class AppointmentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'scheduled_at', 'duration_minutes', 'visit_type', 'reason', 'status', 'notes']
        widgets = {'scheduled_at': DateTimeInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['doctor'].queryset = Doctor.objects.filter(is_active=True).select_related('department')

    def clean(self):
        cleaned = super().clean()
        doctor, when = cleaned.get('doctor'), cleaned.get('scheduled_at')
        if doctor and when:
            clash = Appointment.objects.filter(doctor=doctor, scheduled_at=when).exclude(
                status__in=[Appointment.Status.CANCELLED]).exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(f'{doctor} already has an appointment at that time.')
        return cleaned


class ConsultationForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Consultation
        exclude = ['appointment']
        widgets = {'follow_up_date': DateInput()}


class PrescriptionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['instructions']
        widgets = {'instructions': forms.Textarea(attrs={'rows': 2})}


class PrescriptionItemForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PrescriptionItem
        fields = ['medicine', 'dosage', 'frequency', 'duration_days', 'quantity', 'instructions']


PrescriptionItemFormSet = inlineformset_factory(
    Prescription, PrescriptionItem, form=PrescriptionItemForm, extra=3, can_delete=True)


class LabOrderSelectForm(forms.Form):
    tests = forms.ModelMultipleChoiceField(
        queryset=LabTest.objects.all(), required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 8}),
        help_text='Hold Ctrl to select several tests.')


class LabOrderForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = LabOrder
        fields = ['patient', 'ordered_by', 'test']


class LabResultForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = LabOrder
        fields = ['status', 'result_value', 'is_abnormal', 'result_notes']


class MedicineForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Medicine
        fields = '__all__'
        widgets = {'expiry_date': DateInput()}


class StockAdjustForm(BootstrapMixin, forms.Form):
    quantity = forms.IntegerField(help_text='Positive to add stock, negative to remove.')


class InvoiceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['patient', 'appointment', 'issued_on', 'due_on', 'discount', 'notes']
        widgets = {'issued_on': DateInput(), 'due_on': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['appointment'].queryset = Appointment.objects.select_related('patient', 'doctor')[:0]
        patient = self.initial.get('patient') or self.data.get('patient') or getattr(self.instance, 'patient_id', None)
        if patient:
            self.fields['appointment'].queryset = Appointment.objects.filter(
                patient_id=getattr(patient, 'pk', patient)).select_related('patient', 'doctor')


class InvoiceItemForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['kind', 'description', 'quantity', 'unit_price']


InvoiceItemFormSet = inlineformset_factory(Invoice, InvoiceItem, form=InvoiceItemForm, extra=3, can_delete=True)


class PaymentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'method', 'reference']
