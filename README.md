# Clinic Management System

A Django web application for running an outpatient clinic: patient registration, doctor
schedules, appointments, consultations with vitals and prescriptions, laboratory orders and
results, pharmacy inventory, billing with payments, and reports.

## Stack

- Python 3.13, Django 6.1 (installed in `.venv`)
- SQLite database (`db.sqlite3`)
- Bootstrap 5 + Bootstrap Icons (loaded from CDN)
- Faker (installed for data generation)

## Running it

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in.

## Demo accounts (local development only)

All seeded accounts use the password `Clinic@2026`.

| Username            | Role                                      |
|---------------------|-------------------------------------------|
| `admin`             | Superuser — web app plus `/admin/` panel  |
| `reception`         | Front desk (staff, "Reception" group)     |
| `dr.<name><n>`      | One account per doctor ("Doctors" group)  |

Change these before using the system with real data.

## Modules

| Module        | URL              | What it does |
|---------------|------------------|--------------|
| Dashboard     | `/`              | Today's appointments, KPIs, 14-day trend, pending labs |
| Patients      | `/patients/`     | Register/search patients (auto MRN), full history: visits, consultations, labs, bills |
| Appointments  | `/appointments/` | Book, filter by date/doctor/status, double-booking check, status workflow |
| Consultation  | from appointment | Vitals, diagnosis (ICD-10), prescription lines, lab orders, printable prescription |
| Doctors       | `/doctors/`      | Profiles, departments, shifts, fees, daily schedule |
| Laboratory    | `/lab/`          | Pending work list, result entry, abnormal flagging |
| Pharmacy      | `/pharmacy/`     | Medicine inventory, low-stock alerts, stock adjustments |
| Billing       | `/billing/`      | Invoices (auto-generated from a visit or manual), payments, balances, print |
| Reports       | `/reports/`      | Monthly revenue, department load, outcomes, top diagnoses/medicines, doctor workload |
| Admin         | `/admin/`        | Django admin for every table |

## Data model

`Department` → `Doctor` → `Appointment` ← `Patient`
`Appointment` → `Consultation` → `Prescription` → `PrescriptionItem` → `Medicine`
`Consultation` → `LabOrder` → `LabTest`
`Patient` → `Invoice` → `InvoiceItem`, `Payment`

## Seeding the database

The database is already filled. To rebuild it:

```powershell
python manage.py seed_data --flush
```

Options: `--patients N`, `--appointments N`, `--days-back N`, `--seed N`.
Default volume: 9 departments, 20 doctors, 500 patients, ~3,000 appointments over the last year
plus two weeks ahead, with consultations, prescriptions, lab orders/results, invoices and payments.



## Fresh setup on another machine

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_data
.\.venv\Scripts\python.exe manage.py runserver
```
