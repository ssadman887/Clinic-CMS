from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('patients/', views.patient_list, name='patient_list'),
    path('patients/new/', views.patient_form, name='patient_create'),
    path('patients/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:pk>/edit/', views.patient_form, name='patient_update'),

    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/new/', views.doctor_form, name='doctor_create'),
    path('doctors/<int:pk>/', views.doctor_detail, name='doctor_detail'),
    path('doctors/<int:pk>/edit/', views.doctor_form, name='doctor_update'),

    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/new/', views.appointment_form, name='appointment_create'),
    path('appointments/<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:pk>/edit/', views.appointment_form, name='appointment_update'),
    path('appointments/<int:pk>/status/', views.appointment_status, name='appointment_status'),
    path('appointments/<int:appointment_pk>/consultation/', views.consultation_form, name='consultation_form'),
    path('appointments/<int:appointment_pk>/invoice/', views.invoice_from_appointment, name='invoice_from_appointment'),
    path('consultations/<int:pk>/print/', views.prescription_print, name='prescription_print'),

    path('pharmacy/', views.medicine_list, name='medicine_list'),
    path('pharmacy/new/', views.medicine_form, name='medicine_create'),
    path('pharmacy/<int:pk>/edit/', views.medicine_form, name='medicine_update'),
    path('pharmacy/<int:pk>/adjust/', views.medicine_adjust, name='medicine_adjust'),

    path('lab/', views.lab_order_list, name='lab_list'),
    path('lab/new/', views.lab_order_create, name='lab_create'),
    path('lab/<int:pk>/result/', views.lab_result, name='lab_result'),

    path('billing/', views.invoice_list, name='invoice_list'),
    path('billing/new/', views.invoice_form, name='invoice_create'),
    path('billing/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('billing/<int:pk>/edit/', views.invoice_form, name='invoice_update'),

    path('reports/', views.reports, name='reports'),
]
