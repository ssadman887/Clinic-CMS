from django.contrib import admin

from .models import (Appointment, Consultation, Department, Doctor, Invoice, InvoiceItem, LabOrder,
                     LabTest, Medicine, Patient, Payment, Prescription, PrescriptionItem)

admin.site.site_header = 'Clinic Management System'
admin.site.site_title = 'CMS Admin'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'floor']
    search_fields = ['name']


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'department', 'specialization', 'phone', 'consultation_fee', 'is_active']
    list_filter = ['department', 'is_active']
    search_fields = ['first_name', 'last_name', 'license_no', 'specialization']


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['mrn', 'full_name', 'gender', 'date_of_birth', 'blood_group', 'phone']
    list_filter = ['gender', 'blood_group']
    search_fields = ['mrn', 'first_name', 'last_name', 'phone', 'email']
    readonly_fields = ['mrn']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['scheduled_at', 'patient', 'doctor', 'visit_type', 'status']
    list_filter = ['status', 'visit_type', 'doctor__department']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn', 'reason']
    date_hierarchy = 'scheduled_at'
    autocomplete_fields = ['patient', 'doctor']


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1
    autocomplete_fields = ['medicine']


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    inlines = [PrescriptionItemInline]
    list_display = ['id', 'consultation', 'created_at']


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ['appointment', 'diagnosis', 'icd10_code', 'created_at']
    search_fields = ['diagnosis', 'icd10_code', 'appointment__patient__last_name']


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['name', 'generic_name', 'form', 'strength', 'unit_price', 'stock_quantity', 'reorder_level']
    list_filter = ['form']
    search_fields = ['name', 'generic_name']


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'price', 'normal_range', 'unit']
    list_filter = ['category']
    search_fields = ['name', 'code']


@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ['test', 'patient', 'ordered_by', 'status', 'is_abnormal', 'ordered_at']
    list_filter = ['status', 'is_abnormal', 'test__category']
    search_fields = ['patient__last_name', 'patient__mrn', 'test__name']


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_no', 'patient', 'issued_on', 'status']
    list_filter = ['status']
    search_fields = ['invoice_no', 'patient__last_name', 'patient__mrn']
    inlines = [InvoiceItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'method', 'paid_at']
    list_filter = ['method']
