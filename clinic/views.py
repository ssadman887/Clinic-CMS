from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (AppointmentForm, ConsultationForm, DoctorForm, InvoiceForm, InvoiceItemFormSet,
                    LabOrderForm, LabOrderSelectForm, LabResultForm, MedicineForm, PatientForm, PaymentForm,
                    PrescriptionForm, PrescriptionItemFormSet, StockAdjustForm)
from .models import (Appointment, Consultation, Department, Doctor, Invoice, InvoiceItem, LabOrder, Medicine,
                     Patient, Payment, Prescription, PrescriptionItem)

PAGE_SIZE = 25

LINE_TOTAL = ExpressionWrapper(F('items__unit_price') * F('items__quantity'),
                               output_field=DecimalField(max_digits=12, decimal_places=2))


def paginate(request, qs, size=PAGE_SIZE):
    page = Paginator(qs, size).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return page, params.urlencode()


# --------------------------------------------------------------------------- dashboard

@login_required
def dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    todays = (Appointment.objects.filter(scheduled_at__date=today)
              .select_related('patient', 'doctor').order_by('scheduled_at'))
    revenue_month = Payment.objects.filter(paid_at__date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0
    revenue_today = Payment.objects.filter(paid_at__date=today).aggregate(s=Sum('amount'))['s'] or 0

    # appointments per day over the last 14 days (for the mini chart)
    start = today - timedelta(days=13)
    per_day = dict(Appointment.objects.filter(scheduled_at__date__gte=start, scheduled_at__date__lte=today)
                   .values_list('scheduled_at__date').annotate(c=Count('id')).values_list('scheduled_at__date', 'c'))
    trend = [{'day': start + timedelta(days=i), 'count': per_day.get(start + timedelta(days=i), 0)} for i in range(14)]
    peak = max([t['count'] for t in trend] + [1])
    for t in trend:
        t['pct'] = round(t['count'] * 100 / peak)

    ctx = {
        'today': today,
        'stats': {
            'patients': Patient.objects.count(),
            'new_patients_month': Patient.objects.filter(created_at__date__gte=month_start).count(),
            'doctors': Doctor.objects.filter(is_active=True).count(),
            'appointments_today': todays.count(),
            'pending_labs': LabOrder.objects.filter(status__in=['ordered', 'collected']).count(),
            'unpaid_invoices': Invoice.objects.filter(status__in=['unpaid', 'partial']).count(),
            'revenue_today': revenue_today,
            'revenue_month': revenue_month,
            'low_stock': Medicine.objects.filter(stock_quantity__lte=F('reorder_level')).count(),
        },
        'todays': todays[:15],
        'trend': trend,
        'upcoming': (Appointment.objects.filter(scheduled_at__gt=timezone.now(), status='scheduled')
                     .select_related('patient', 'doctor').order_by('scheduled_at')[:8]),
        'recent_labs': LabOrder.objects.filter(status__in=['ordered', 'collected'])
                       .select_related('patient', 'test')[:8],
    }
    return render(request, 'clinic/dashboard.html', ctx)


# --------------------------------------------------------------------------- patients

@login_required
def patient_list(request):
    qs = Patient.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(mrn__icontains=q) |
                       Q(phone__icontains=q) | Q(email__icontains=q))
    if g := request.GET.get('gender'):
        qs = qs.filter(gender=g)
    if b := request.GET.get('blood'):
        qs = qs.filter(blood_group=b)
    page, params = paginate(request, qs)
    return render(request, 'clinic/patient_list.html', {
        'page': page, 'params': params, 'q': q, 'blood_groups': Patient.BLOOD_GROUPS,
        'genders': Patient.GENDER_CHOICES})


@login_required
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    return render(request, 'clinic/patient_detail.html', {
        'patient': patient,
        'appointments': patient.appointments.select_related('doctor')[:20],
        'consultations': Consultation.objects.filter(appointment__patient=patient)
                         .select_related('appointment__doctor').prefetch_related('prescription__items__medicine')[:20],
        'lab_orders': patient.lab_orders.select_related('test')[:20],
        'invoices': patient.invoices.prefetch_related('items', 'payments')[:20],
    })


@login_required
def patient_form(request, pk=None):
    patient = get_object_or_404(Patient, pk=pk) if pk else None
    form = PatientForm(request.POST or None, instance=patient)
    if request.method == 'POST' and form.is_valid():
        patient = form.save()
        messages.success(request, f'Patient {patient.full_name} saved.')
        return redirect(patient)
    return render(request, 'clinic/form.html', {
        'form': form, 'title': 'Edit patient' if pk else 'Register patient',
        'cancel_url': patient.get_absolute_url() if patient else '/patients/'})


# --------------------------------------------------------------------------- doctors

@login_required
def doctor_list(request):
    qs = Doctor.objects.select_related('department').annotate(
        n_appts=Count('appointments', distinct=True))
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(specialization__icontains=q))
    if d := request.GET.get('department'):
        qs = qs.filter(department_id=d)
    return render(request, 'clinic/doctor_list.html', {
        'doctors': qs, 'q': q, 'departments': Department.objects.all()})


@login_required
def doctor_detail(request, pk):
    doctor = get_object_or_404(Doctor.objects.select_related('department'), pk=pk)
    day = request.GET.get('date')
    try:
        day = timezone.datetime.fromisoformat(day).date() if day else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    schedule = doctor.appointments.filter(scheduled_at__date=day).select_related('patient').order_by('scheduled_at')
    stats = doctor.appointments.aggregate(
        total=Count('id'), completed=Count('id', filter=Q(status='completed')),
        patients=Count('patient', distinct=True))
    return render(request, 'clinic/doctor_detail.html', {
        'doctor': doctor, 'schedule': schedule, 'day': day, 'stats': stats,
        'prev_day': day - timedelta(days=1), 'next_day': day + timedelta(days=1)})


@login_required
def doctor_form(request, pk=None):
    doctor = get_object_or_404(Doctor, pk=pk) if pk else None
    form = DoctorForm(request.POST or None, instance=doctor)
    if request.method == 'POST' and form.is_valid():
        doctor = form.save()
        messages.success(request, f'{doctor} saved.')
        return redirect(doctor)
    return render(request, 'clinic/form.html', {
        'form': form, 'title': 'Edit doctor' if pk else 'Add doctor', 'cancel_url': '/doctors/'})


# --------------------------------------------------------------------------- appointments

@login_required
def appointment_list(request):
    qs = Appointment.objects.select_related('patient', 'doctor', 'doctor__department')
    f = request.GET
    if f.get('date'):
        qs = qs.filter(scheduled_at__date=f['date'])
    if f.get('status'):
        qs = qs.filter(status=f['status'])
    if f.get('doctor'):
        qs = qs.filter(doctor_id=f['doctor'])
    if q := f.get('q', '').strip():
        qs = qs.filter(Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q) |
                       Q(patient__mrn__icontains=q) | Q(reason__icontains=q))
    page, params = paginate(request, qs)
    return render(request, 'clinic/appointment_list.html', {
        'page': page, 'params': params, 'statuses': Appointment.Status.choices,
        'doctors': Doctor.objects.filter(is_active=True), 'f': f})


@login_required
def appointment_detail(request, pk):
    appt = get_object_or_404(Appointment.objects.select_related('patient', 'doctor__department'), pk=pk)
    consultation = getattr(appt, 'consultation', None) if hasattr(appt, 'consultation') else None
    return render(request, 'clinic/appointment_detail.html', {
        'appt': appt, 'consultation': consultation, 'invoices': appt.invoices.all(),
        'statuses': Appointment.Status.choices})


@login_required
def appointment_form(request, pk=None):
    appt = get_object_or_404(Appointment, pk=pk) if pk else None
    initial = {}
    if not appt:
        for key in ('patient', 'doctor'):
            if request.GET.get(key):
                initial[key] = request.GET[key]
    form = AppointmentForm(request.POST or None, instance=appt, initial=initial)
    if request.method == 'POST' and form.is_valid():
        appt = form.save()
        messages.success(request, 'Appointment saved.')
        return redirect(appt)
    return render(request, 'clinic/form.html', {
        'form': form, 'title': 'Edit appointment' if pk else 'Book appointment', 'cancel_url': '/appointments/'})


@login_required
@require_POST
def appointment_status(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    status = request.POST.get('status')
    if status in Appointment.Status.values:
        appt.status = status
        appt.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Status changed to {appt.get_status_display()}.')
    return redirect(request.POST.get('next') or appt.get_absolute_url())


# --------------------------------------------------------------------------- consultation / prescription

@login_required
def consultation_form(request, appointment_pk):
    appt = get_object_or_404(Appointment.objects.select_related('patient', 'doctor'), pk=appointment_pk)
    consultation = getattr(appt, 'consultation', None) if hasattr(appt, 'consultation') else None
    prescription = getattr(consultation, 'prescription', None) if consultation and hasattr(
        consultation, 'prescription') else None

    cform = ConsultationForm(request.POST or None, instance=consultation, prefix='c')
    pform = PrescriptionForm(request.POST or None, instance=prescription, prefix='p')
    formset = PrescriptionItemFormSet(request.POST or None, instance=prescription or Prescription(), prefix='items')
    labform = LabOrderSelectForm(request.POST or None, prefix='lab')

    if request.method == 'POST' and cform.is_valid() and pform.is_valid() and formset.is_valid() and labform.is_valid():
        with transaction.atomic():
            consultation = cform.save(commit=False)
            consultation.appointment = appt
            consultation.save()
            prescription = pform.save(commit=False)
            prescription.consultation = consultation
            prescription.save()
            formset.instance = prescription
            formset.save()
            for test in labform.cleaned_data['tests']:
                LabOrder.objects.create(patient=appt.patient, consultation=consultation,
                                        ordered_by=appt.doctor, test=test)
            if appt.status != Appointment.Status.COMPLETED:
                appt.status = Appointment.Status.COMPLETED
                appt.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Consultation saved and appointment marked completed.')
        return redirect(appt)

    return render(request, 'clinic/consultation_form.html', {
        'appt': appt, 'cform': cform, 'pform': pform, 'formset': formset, 'labform': labform,
        'existing_labs': consultation.lab_orders.select_related('test') if consultation else []})


@login_required
def prescription_print(request, pk):
    consultation = get_object_or_404(
        Consultation.objects.select_related('appointment__patient', 'appointment__doctor__department'), pk=pk)
    return render(request, 'clinic/prescription_print.html', {
        'c': consultation,
        'items': PrescriptionItem.objects.filter(prescription__consultation=consultation).select_related('medicine'),
        'labs': consultation.lab_orders.select_related('test')})


# --------------------------------------------------------------------------- pharmacy

@login_required
def medicine_list(request):
    qs = Medicine.objects.all()
    if q := request.GET.get('q', '').strip():
        qs = qs.filter(Q(name__icontains=q) | Q(generic_name__icontains=q) | Q(manufacturer__icontains=q))
    if request.GET.get('low'):
        qs = qs.filter(stock_quantity__lte=F('reorder_level'))
    if form := request.GET.get('form'):
        qs = qs.filter(form=form)
    page, params = paginate(request, qs)
    return render(request, 'clinic/medicine_list.html', {
        'page': page, 'params': params, 'forms': Medicine.FORMS, 'adjust_form': StockAdjustForm()})


@login_required
def medicine_form(request, pk=None):
    med = get_object_or_404(Medicine, pk=pk) if pk else None
    form = MedicineForm(request.POST or None, instance=med)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Medicine saved.')
        return redirect('medicine_list')
    return render(request, 'clinic/form.html', {
        'form': form, 'title': 'Edit medicine' if pk else 'Add medicine', 'cancel_url': '/pharmacy/'})


@login_required
@require_POST
def medicine_adjust(request, pk):
    med = get_object_or_404(Medicine, pk=pk)
    form = StockAdjustForm(request.POST)
    if form.is_valid():
        med.stock_quantity = max(0, med.stock_quantity + form.cleaned_data['quantity'])
        med.save(update_fields=['stock_quantity', 'updated_at'])
        messages.success(request, f'{med.name} stock is now {med.stock_quantity}.')
    return redirect(request.POST.get('next') or 'medicine_list')


# --------------------------------------------------------------------------- lab

@login_required
def lab_order_list(request):
    qs = LabOrder.objects.select_related('patient', 'test', 'ordered_by')
    status = request.GET.get('status', 'pending')
    if status == 'pending':
        qs = qs.filter(status__in=['ordered', 'collected'])
    elif status:
        qs = qs.filter(status=status)
    if q := request.GET.get('q', '').strip():
        qs = qs.filter(Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q) |
                       Q(patient__mrn__icontains=q) | Q(test__name__icontains=q))
    page, params = paginate(request, qs)
    return render(request, 'clinic/lab_list.html', {
        'page': page, 'params': params, 'status': status, 'statuses': LabOrder.Status.choices})


@login_required
def lab_order_create(request):
    form = LabOrderForm(request.POST or None, initial={'patient': request.GET.get('patient')})
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Lab test ordered.')
        return redirect('lab_list')
    return render(request, 'clinic/form.html', {'form': form, 'title': 'Order lab test', 'cancel_url': '/lab/'})


@login_required
def lab_result(request, pk):
    order = get_object_or_404(LabOrder.objects.select_related('patient', 'test'), pk=pk)
    form = LabResultForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        order = form.save(commit=False)
        if order.status == LabOrder.Status.COMPLETED and not order.completed_at:
            order.completed_at = timezone.now()
        order.save()
        messages.success(request, 'Lab result saved.')
        return redirect('lab_list')
    return render(request, 'clinic/form.html', {
        'form': form, 'title': f'Result: {order.test.name} — {order.patient.full_name}',
        'subtitle': f'Normal range: {order.test.normal_range} {order.test.unit}', 'cancel_url': '/lab/'})


# --------------------------------------------------------------------------- billing

@login_required
def invoice_list(request):
    qs = Invoice.objects.select_related('patient').annotate(
        subtotal_db=Sum(LINE_TOTAL)).order_by('-issued_on', '-id')
    if s := request.GET.get('status'):
        qs = qs.filter(status=s)
    if q := request.GET.get('q', '').strip():
        qs = qs.filter(Q(invoice_no__icontains=q) | Q(patient__first_name__icontains=q) |
                       Q(patient__last_name__icontains=q) | Q(patient__mrn__icontains=q))
    page, params = paginate(request, qs)
    return render(request, 'clinic/invoice_list.html', {
        'page': page, 'params': params, 'statuses': Invoice.Status.choices})


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('patient', 'appointment__doctor'), pk=pk)
    form = PaymentForm(request.POST or None, initial={'amount': invoice.balance})
    if request.method == 'POST' and form.is_valid():
        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.received_by = request.user
        payment.save()
        invoice.refresh_status()
        messages.success(request, f'Payment of {payment.amount} recorded.')
        return redirect(invoice)
    return render(request, 'clinic/invoice_detail.html', {'invoice': invoice, 'form': form})


@login_required
def invoice_form(request, pk=None):
    invoice = get_object_or_404(Invoice, pk=pk) if pk else None
    form = InvoiceForm(request.POST or None, instance=invoice,
                       initial={'patient': request.GET.get('patient')} if not pk else None)
    formset = InvoiceItemFormSet(request.POST or None, instance=invoice or Invoice(), prefix='items')
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            invoice = form.save()
            formset.instance = invoice
            formset.save()
            invoice.refresh_status()
        messages.success(request, f'Invoice {invoice.invoice_no} saved.')
        return redirect(invoice)
    return render(request, 'clinic/invoice_form.html', {
        'form': form, 'formset': formset, 'title': f'Edit {invoice}' if pk else 'New invoice'})


@login_required
@require_POST
def invoice_from_appointment(request, appointment_pk):
    appt = get_object_or_404(Appointment.objects.select_related('patient', 'doctor'), pk=appointment_pk)
    existing = appt.invoices.exclude(status=Invoice.Status.VOID).first()
    if existing:
        messages.info(request, f'This visit is already billed on {existing.invoice_no}.')
        return redirect(existing)
    with transaction.atomic():
        invoice = Invoice.objects.create(patient=appt.patient, appointment=appt,
                                         due_on=timezone.localdate() + timedelta(days=14))
        InvoiceItem.objects.create(invoice=invoice, kind='consultation',
                                   description=f'Consultation — {appt.doctor}', unit_price=appt.doctor.consultation_fee)
        if hasattr(appt, 'consultation'):
            for lo in appt.consultation.lab_orders.select_related('test').exclude(status='cancelled'):
                InvoiceItem.objects.create(invoice=invoice, kind='lab', description=lo.test.name,
                                           unit_price=lo.test.price)
    messages.success(request, f'Invoice {invoice.invoice_no} created.')
    return redirect(invoice)


# --------------------------------------------------------------------------- reports

@login_required
def reports(request):
    year_ago = timezone.localdate().replace(day=1) - timedelta(days=330)
    revenue = list(Payment.objects.filter(paid_at__date__gte=year_ago)
                   .annotate(m=TruncMonth('paid_at')).values('m').annotate(total=Sum('amount')).order_by('m'))
    peak = max([r['total'] for r in revenue] + [Decimal(1)])
    for r in revenue:
        r['pct'] = round(r['total'] * 100 / peak)

    by_dept = list(Department.objects.annotate(
        total=Count('doctors__appointments'),
        completed=Count('doctors__appointments', filter=Q(doctors__appointments__status='completed')),
    ).order_by('-total'))
    peak_d = max([d.total for d in by_dept] + [1])
    for d in by_dept:
        d.pct = round(d.total * 100 / peak_d)

    status_split = Appointment.objects.values('status').annotate(c=Count('id')).order_by('-c')
    total_appts = sum(s['c'] for s in status_split) or 1
    status_split = [{**s, 'label': Appointment.Status(s['status']).label, 'pct': round(s['c'] * 100 / total_appts)}
                    for s in status_split]

    return render(request, 'clinic/reports.html', {
        'revenue': revenue,
        'by_dept': by_dept,
        'status_split': status_split,
        'top_diagnoses': Consultation.objects.values('diagnosis', 'icd10_code')
                         .annotate(c=Count('id')).order_by('-c')[:10],
        'top_medicines': PrescriptionItem.objects.values('medicine__name', 'medicine__strength')
                         .annotate(c=Count('id'), qty=Sum('quantity')).order_by('-c')[:10],
        'top_doctors': Doctor.objects.annotate(
            done=Count('appointments', filter=Q(appointments__status='completed'))).order_by('-done')[:10],
        'outstanding': sum((i.balance for i in Invoice.objects.filter(status__in=['unpaid', 'partial'])
                            .prefetch_related('items', 'payments')), Decimal('0')),
        'lab_abnormal': LabOrder.objects.filter(status='completed', is_abnormal=True).count(),
        'lab_completed': LabOrder.objects.filter(status='completed').count(),
    })
