"""
Fill the database with realistic demo data.

    python manage.py seed_data            # ~20 doctors, 500 patients, ~3000 appointments
    python manage.py seed_data --patients 2000 --appointments 12000
    python manage.py seed_data --flush    # wipe clinic data first

Login accounts created (see README.md for passwords).
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from clinic.models import (Appointment, Consultation, Department, Doctor, Invoice, InvoiceItem, LabOrder, LabTest,
                           Medicine, Patient, Payment, Prescription, PrescriptionItem)

# --------------------------------------------------------------------------- reference data

MALE_FIRST = ['Abdul', 'Rahim', 'Karim', 'Tanvir', 'Sakib', 'Rafiq', 'Mahmud', 'Imran', 'Arif', 'Hasan', 'Nayeem',
              'Fahim', 'Rakib', 'Shahid', 'Jamal', 'Kamal', 'Mizanur', 'Habib', 'Rashed', 'Sohel', 'Tariq', 'Zahid',
              'Anisur', 'Mehedi', 'Sabbir', 'Rubel', 'Shafiq', 'Farhan', 'Ashraf', 'Nazmul', 'Rezaul', 'Mamun',
              'Touhid', 'Ibrahim', 'Yusuf', 'Shakil', 'Riyad', 'Ayaan', 'Arnob', 'Sajid']
FEMALE_FIRST = ['Fatema', 'Ayesha', 'Nusrat', 'Sadia', 'Farzana', 'Tahmina', 'Sharmin', 'Nasrin', 'Rumana', 'Shirin',
                'Jannat', 'Tasnim', 'Sumaiya', 'Mim', 'Rokeya', 'Hasina', 'Nadia', 'Lamia', 'Anika', 'Sabrina',
                'Shamima', 'Rehana', 'Moushumi', 'Tania', 'Afroza', 'Kulsum', 'Shathi', 'Faria', 'Ishrat', 'Rifat',
                'Maliha', 'Zara', 'Mehjabin', 'Samira', 'Raisa', 'Puja', 'Priya', 'Laboni', 'Mitu', 'Sanjida']
LAST_NAMES = ['Rahman', 'Hossain', 'Islam', 'Ahmed', 'Khan', 'Chowdhury', 'Uddin', 'Akter', 'Begum', 'Sarker',
              'Miah', 'Alam', 'Haque', 'Karim', 'Talukder', 'Siddique', 'Mollah', 'Bhuiyan', 'Sheikh', 'Das',
              'Roy', 'Saha', 'Paul', 'Biswas', 'Mondal', 'Majumder', 'Kabir', 'Hasan', 'Mahmud', 'Sultana']
AREAS = ['Dhanmondi', 'Mirpur', 'Uttara', 'Gulshan', 'Banani', 'Mohammadpur', 'Bashundhara', 'Motijheel',
         'Shantinagar', 'Lalbagh', 'Badda', 'Rampura', 'Khilgaon', 'Tejgaon', 'Farmgate', 'Jatrabari', 'Wari',
         'Azimpur', 'Shyamoli', 'Malibagh']
INSURERS = ['', '', '', '', 'Green Delta Insurance', 'MetLife Bangladesh', 'Pragati Life', 'Guardian Life']
ALLERGIES = ['', '', '', '', '', '', 'Penicillin', 'Sulfa drugs', 'NSAIDs', 'Peanuts', 'Dust mites', 'Seafood',
             'Latex', 'Aspirin']
CHRONIC = ['', '', '', '', 'Hypertension', 'Type 2 diabetes', 'Asthma', 'Hypothyroidism', 'Hypertension, Type 2 diabetes',
           'COPD', 'Chronic kidney disease (stage 2)', 'Osteoarthritis']

DEPARTMENTS = [
    ('General Medicine', 'Ground', 'Primary care and internal medicine'),
    ('Cardiology', '2nd', 'Heart and blood vessel disorders'),
    ('Pediatrics', '1st', 'Care for infants, children and adolescents'),
    ('Orthopedics', '3rd', 'Bones, joints and musculoskeletal system'),
    ('Dermatology', '1st', 'Skin, hair and nail conditions'),
    ('Gynecology & Obstetrics', '2nd', "Women's health and maternity"),
    ('ENT', '3rd', 'Ear, nose and throat'),
    ('Neurology', '4th', 'Brain, spinal cord and nerves'),
    ('Endocrinology', '4th', 'Diabetes, thyroid and hormonal disorders'),
]

SPECIALIZATION = {
    'General Medicine': ('Internal Medicine', 'MBBS, FCPS (Medicine)', 600),
    'Cardiology': ('Cardiologist', 'MBBS, MD (Cardiology)', 1200),
    'Pediatrics': ('Pediatrician', 'MBBS, DCH, FCPS (Paediatrics)', 800),
    'Orthopedics': ('Orthopedic Surgeon', 'MBBS, MS (Orthopaedics)', 1000),
    'Dermatology': ('Dermatologist', 'MBBS, DDV', 800),
    'Gynecology & Obstetrics': ('Gynecologist', 'MBBS, FCPS (Gynae & Obs)', 1000),
    'ENT': ('ENT Specialist', 'MBBS, DLO, MS (ENT)', 800),
    'Neurology': ('Neurologist', 'MBBS, MD (Neurology)', 1500),
    'Endocrinology': ('Endocrinologist', 'MBBS, MD (Endocrinology)', 1200),
}
DOCTORS_PER_DEPT = {'General Medicine': 4, 'Cardiology': 2, 'Pediatrics': 3, 'Orthopedics': 2, 'Dermatology': 2,
                    'Gynecology & Obstetrics': 2, 'ENT': 2, 'Neurology': 1, 'Endocrinology': 2}
DAY_SETS = ['Sat,Sun,Mon,Tue,Wed', 'Sun,Mon,Tue,Wed,Thu', 'Sat,Mon,Wed,Thu', 'Sun,Tue,Thu,Sat', 'Sat,Sun,Mon,Tue,Wed,Thu']
SHIFTS = [(time(9), time(13)), (time(10), time(14)), (time(14), time(18)), (time(16), time(21)), (time(9), time(17))]
WEEKDAY = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}

# name, generic, form, strength, manufacturer, price
MEDICINES = [
    ('Napa', 'Paracetamol', 'Tablet', '500 mg', 'Beximco', '1.20'),
    ('Napa Extra', 'Paracetamol + Caffeine', 'Tablet', '565 mg', 'Beximco', '2.50'),
    ('Napa', 'Paracetamol', 'Syrup', '120 mg/5 ml', 'Beximco', '35.00'),
    ('Ace', 'Paracetamol', 'Tablet', '500 mg', 'Square', '1.20'),
    ('Seclo', 'Omeprazole', 'Capsule', '20 mg', 'Square', '6.00'),
    ('Sergel', 'Esomeprazole', 'Capsule', '20 mg', 'Healthcare', '7.00'),
    ('Pantonix', 'Pantoprazole', 'Tablet', '40 mg', 'Incepta', '8.00'),
    ('Antacid Plus', 'Aluminium + Magnesium hydroxide', 'Syrup', '200 ml', 'Square', '70.00'),
    ('Azithrocin', 'Azithromycin', 'Tablet', '500 mg', 'Beximco', '40.00'),
    ('Zimax', 'Azithromycin', 'Syrup', '200 mg/5 ml', 'Square', '120.00'),
    ('Moxacil', 'Amoxicillin', 'Capsule', '500 mg', 'Square', '9.00'),
    ('Fimoxyl', 'Amoxicillin', 'Syrup', '125 mg/5 ml', 'Opsonin', '60.00'),
    ('Cef-3', 'Cefixime', 'Capsule', '200 mg', 'Square', '35.00'),
    ('Ciprocin', 'Ciprofloxacin', 'Tablet', '500 mg', 'Square', '15.00'),
    ('Flagyl', 'Metronidazole', 'Tablet', '400 mg', 'Sanofi', '2.00'),
    ('Fexo', 'Fexofenadine', 'Tablet', '120 mg', 'Square', '9.00'),
    ('Alatrol', 'Cetirizine', 'Tablet', '10 mg', 'Square', '3.00'),
    ('Monas', 'Montelukast', 'Tablet', '10 mg', 'Acme', '16.00'),
    ('Ventolin', 'Salbutamol', 'Inhaler', '100 mcg', 'GSK', '250.00'),
    ('Seretide', 'Salmeterol + Fluticasone', 'Inhaler', '25/250 mcg', 'GSK', '950.00'),
    ('Tusca', 'Dextromethorphan + Guaifenesin', 'Syrup', '100 ml', 'Square', '85.00'),
    ('Amdocal', 'Amlodipine', 'Tablet', '5 mg', 'Beximco', '5.00'),
    ('Osartil', 'Losartan', 'Tablet', '50 mg', 'Incepta', '8.00'),
    ('Bisocor', 'Bisoprolol', 'Tablet', '5 mg', 'Healthcare', '7.00'),
    ('Ecosprin', 'Aspirin', 'Tablet', '75 mg', 'ACI', '0.80'),
    ('Clopid', 'Clopidogrel', 'Tablet', '75 mg', 'Square', '10.00'),
    ('Rosuva', 'Rosuvastatin', 'Tablet', '10 mg', 'Square', '15.00'),
    ('Atova', 'Atorvastatin', 'Tablet', '20 mg', 'Beximco', '12.00'),
    ('Lasix', 'Furosemide', 'Tablet', '40 mg', 'Sanofi', '1.50'),
    ('Nitrocard', 'Glyceryl trinitrate', 'Tablet', '2.6 mg', 'Square', '4.00'),
    ('Comet', 'Metformin', 'Tablet', '500 mg', 'Square', '4.00'),
    ('Secrin', 'Glimepiride', 'Tablet', '2 mg', 'Square', '8.00'),
    ('Linagliptin-BD', 'Linagliptin', 'Tablet', '5 mg', 'Incepta', '30.00'),
    ('Mixtard 30', 'Human insulin 30/70', 'Injection', '100 IU/ml', 'Novo Nordisk', '450.00'),
    ('Thyrox', 'Levothyroxine', 'Tablet', '50 mcg', 'Renata', '1.50'),
    ('Neo-Mercazole', 'Carbimazole', 'Tablet', '5 mg', 'Healthcare', '3.00'),
    ('Naprosyn', 'Naproxen', 'Tablet', '500 mg', 'Radiant', '10.00'),
    ('Clofenac', 'Diclofenac', 'Tablet', '50 mg', 'Square', '2.00'),
    ('Clofenac Gel', 'Diclofenac', 'Ointment', '1% 20 g', 'Square', '80.00'),
    ('Tory', 'Etoricoxib', 'Tablet', '90 mg', 'Beximco', '14.00'),
    ('Myolax', 'Tolperisone', 'Tablet', '150 mg', 'Renata', '6.00'),
    ('Calbo-D', 'Calcium + Vitamin D3', 'Tablet', '500 mg', 'Square', '9.00'),
    ('D-Rise', 'Cholecalciferol', 'Capsule', '40000 IU', 'Beximco', '45.00'),
    ('Neurobion', 'Vitamin B1+B6+B12', 'Tablet', '—', 'Merck', '8.00'),
    ('Pregaba', 'Pregabalin', 'Capsule', '75 mg', 'Incepta', '15.00'),
    ('Sumatriptan BD', 'Sumatriptan', 'Tablet', '50 mg', 'Square', '40.00'),
    ('Flunarizine', 'Flunarizine', 'Tablet', '5 mg', 'Opsonin', '4.00'),
    ('Rivotril', 'Clonazepam', 'Tablet', '0.5 mg', 'Roche', '6.00'),
    ('Epilim', 'Sodium valproate', 'Tablet', '200 mg', 'Sanofi', '7.00'),
    ('Fungidal', 'Clotrimazole', 'Ointment', '1% 15 g', 'Square', '60.00'),
    ('Flucon', 'Fluconazole', 'Capsule', '150 mg', 'Beximco', '30.00'),
    ('Betnovate', 'Betamethasone', 'Ointment', '0.1% 15 g', 'GSK', '75.00'),
    ('Isotin', 'Isotretinoin', 'Capsule', '20 mg', 'Square', '40.00'),
    ('Permin', 'Permethrin', 'Ointment', '5% 30 g', 'Acme', '110.00'),
    ('Otosporin', 'Polymyxin + Neomycin + HC', 'Drops', '5 ml', 'GSK', '120.00'),
    ('Nasivion', 'Oxymetazoline', 'Drops', '0.05% 10 ml', 'Merck', '60.00'),
    ('Avamys', 'Fluticasone furoate', 'Drops', '27.5 mcg', 'GSK', '650.00'),
    ('Folison', 'Folic acid', 'Tablet', '5 mg', 'Square', '1.00'),
    ('Ferrous-Zn', 'Iron + Folic acid + Zinc', 'Capsule', '—', 'Square', '5.00'),
    ('Mefenamic', 'Mefenamic acid', 'Tablet', '500 mg', 'ACI', '4.00'),
    ('Ondansetron', 'Ondansetron', 'Tablet', '8 mg', 'Incepta', '10.00'),
    ('ORS Saline', 'Oral rehydration salts', 'Syrup', '500 ml sachet', 'SMC', '6.00'),
    ('Zinc-B', 'Zinc sulphate', 'Syrup', '100 ml', 'ACI', '50.00'),
]

# name, code, category, price, low, high, unit, decimals  (low=None → qualitative test)
LAB_TESTS = [
    ('Complete Blood Count (Hb)', 'CBC', 'Hematology', 400, 12.0, 16.5, 'g/dL', 1),
    ('ESR', 'ESR', 'Hematology', 200, 0, 20, 'mm/1st hr', 0),
    ('Platelet count', 'PLT', 'Hematology', 250, 150, 450, 'x10³/µL', 0),
    ('Fasting Blood Sugar', 'FBS', 'Biochemistry', 150, 3.9, 5.6, 'mmol/L', 1),
    ('Random Blood Sugar', 'RBS', 'Biochemistry', 150, 3.9, 7.8, 'mmol/L', 1),
    ('HbA1c', 'HBA1C', 'Biochemistry', 900, 4.0, 5.6, '%', 1),
    ('Serum Creatinine', 'CREAT', 'Biochemistry', 400, 0.6, 1.2, 'mg/dL', 2),
    ('Lipid Profile (Total cholesterol)', 'LIPID', 'Biochemistry', 1000, 120, 200, 'mg/dL', 0),
    ('SGPT (ALT)', 'ALT', 'Biochemistry', 400, 7, 40, 'U/L', 0),
    ('Serum Uric Acid', 'URIC', 'Biochemistry', 400, 3.5, 7.2, 'mg/dL', 1),
    ('Serum Electrolytes (Na)', 'ELEC', 'Biochemistry', 800, 135, 145, 'mmol/L', 0),
    ('TSH', 'TSH', 'Hormone', 800, 0.4, 4.0, 'mIU/L', 2),
    ('Free T4', 'FT4', 'Hormone', 800, 0.8, 1.8, 'ng/dL', 2),
    ('Vitamin D (25-OH)', 'VITD', 'Hormone', 2500, 30, 100, 'ng/mL', 0),
    ('Troponin I', 'TROP', 'Cardiac', 1500, 0.0, 0.04, 'ng/mL', 3),
    ('CRP', 'CRP', 'Immunology', 600, 0, 6, 'mg/L', 1),
    ('Dengue NS1 Antigen', 'NS1', 'Immunology', 500, None, None, '', 0),
    ('Widal Test', 'WIDAL', 'Immunology', 350, None, None, '', 0),
    ('Urine R/E', 'URE', 'Clinical Pathology', 200, None, None, '', 0),
    ('Stool R/E', 'SRE', 'Clinical Pathology', 200, None, None, '', 0),
    ('Chest X-Ray (P/A view)', 'CXR', 'Radiology', 600, None, None, '', 0),
    ('X-Ray Knee (AP/Lat)', 'XKNEE', 'Radiology', 800, None, None, '', 0),
    ('USG Whole Abdomen', 'USGWA', 'Radiology', 1800, None, None, '', 0),
    ('ECG (12 lead)', 'ECG', 'Cardiac', 400, None, None, '', 0),
    ('Echocardiogram', 'ECHO', 'Cardiac', 2500, None, None, '', 0),
    ('MRI Brain', 'MRIB', 'Radiology', 9000, None, None, '', 0),
    ('Pure Tone Audiometry', 'PTA', 'ENT', 1000, None, None, '', 0),
    ('Skin Scraping for Fungus', 'KOH', 'Microbiology', 400, None, None, '', 0),
]
QUALITATIVE = {
    'NS1': (['Negative'], ['Positive']),
    'WIDAL': (['TO 1:40, TH 1:40 — Not significant'], ['TO 1:160, TH 1:320 — Significant']),
    'URE': (['No abnormality detected'], ['Pus cells 15-20/HPF, Protein (+)']),
    'SRE': (['No ova, cyst or parasite seen'], ['Cyst of E. histolytica found']),
    'CXR': (['Normal study'], ['Patchy opacity in right lower zone', 'Cardiomegaly (CTR 0.56)']),
    'XKNEE': (['No bony abnormality'], ['Reduced joint space with osteophytes']),
    'USGWA': (['Normal study'], ['Fatty liver (grade I)', 'Right renal calculus 6 mm']),
    'ECG': (['Normal sinus rhythm'], ['ST depression in V4-V6', 'Left ventricular hypertrophy']),
    'ECHO': (['Normal LV function, EF 62%'], ['Mild LV dysfunction, EF 45%']),
    'MRIB': (['No significant abnormality'], ['Small chronic lacunar infarct, left basal ganglia']),
    'PTA': (['Hearing within normal limits'], ['Mild sensorineural hearing loss, left ear']),
    'KOH': (['Fungal elements not seen'], ['Fungal hyphae seen']),
}

# department -> list of (complaint, diagnosis, icd10, [medicine generic names], [lab codes])
CASES = {
    'General Medicine': [
        ('Fever and body ache for 3 days', 'Viral fever', 'B34.9', ['Paracetamol', 'Cetirizine'], ['CBC', 'NS1']),
        ('High fever with headache', 'Dengue fever', 'A90', ['Paracetamol', 'Oral rehydration salts'], ['CBC', 'PLT', 'NS1']),
        ('Prolonged fever, abdominal pain', 'Enteric fever', 'A01.0', ['Cefixime', 'Paracetamol'], ['CBC', 'WIDAL']),
        ('Burning epigastric pain', 'Gastritis', 'K29.7', ['Omeprazole', 'Aluminium + Magnesium hydroxide'], []),
        ('Heartburn after meals', 'GERD', 'K21.9', ['Esomeprazole'], []),
        ('Loose stools and cramps', 'Acute gastroenteritis', 'A09', ['Oral rehydration salts', 'Metronidazole', 'Zinc sulphate'], ['SRE']),
        ('Burning micturition', 'Urinary tract infection', 'N39.0', ['Ciprofloxacin', 'Paracetamol'], ['URE', 'CBC']),
        ('Cough and sore throat', 'Upper respiratory tract infection', 'J06.9', ['Azithromycin', 'Dextromethorphan + Guaifenesin', 'Fexofenadine'], []),
        ('Headache and dizziness, high BP reading', 'Essential hypertension', 'I10', ['Amlodipine', 'Losartan'], ['CREAT', 'ELEC', 'LIPID']),
        ('Fatigue and weakness', 'Iron deficiency anaemia', 'D50.9', ['Iron + Folic acid + Zinc'], ['CBC']),
        ('Routine check-up', 'General health examination', 'Z00.0', ['Calcium + Vitamin D3'], ['CBC', 'FBS', 'LIPID', 'CREAT']),
    ],
    'Cardiology': [
        ('Chest pain on exertion', 'Stable angina', 'I20.9', ['Aspirin', 'Glyceryl trinitrate', 'Bisoprolol', 'Atorvastatin'], ['ECG', 'TROP', 'LIPID']),
        ('Breathlessness and leg swelling', 'Congestive heart failure', 'I50.9', ['Furosemide', 'Bisoprolol', 'Losartan'], ['ECHO', 'CXR', 'ELEC']),
        ('Palpitations', 'Palpitations, unspecified', 'R00.2', ['Bisoprolol'], ['ECG', 'TSH']),
        ('Follow-up of high blood pressure', 'Hypertensive heart disease', 'I11.9', ['Amlodipine', 'Losartan', 'Rosuvastatin'], ['ECG', 'ECHO']),
        ('Post-MI follow-up', 'Old myocardial infarction', 'I25.2', ['Aspirin', 'Clopidogrel', 'Rosuvastatin', 'Bisoprolol'], ['LIPID', 'ECG']),
        ('High cholesterol on report', 'Hyperlipidaemia', 'E78.5', ['Rosuvastatin'], ['LIPID', 'ALT']),
    ],
    'Pediatrics': [
        ('Fever and runny nose', 'Common cold (child)', 'J00', ['Paracetamol', 'Cetirizine'], []),
        ('Diarrhoea for 2 days', 'Acute watery diarrhoea', 'A09', ['Oral rehydration salts', 'Zinc sulphate'], ['SRE']),
        ('Cough and wheeze', 'Bronchiolitis', 'J21.9', ['Salbutamol', 'Paracetamol'], ['CXR']),
        ('Ear pain and fever', 'Acute otitis media', 'H66.9', ['Amoxicillin', 'Paracetamol'], []),
        ('Routine vaccination visit', 'Immunization encounter', 'Z23', ['Paracetamol'], []),
        ('Sore throat, fever', 'Acute tonsillitis', 'J03.9', ['Amoxicillin', 'Paracetamol'], ['CBC']),
    ],
    'Orthopedics': [
        ('Knee pain while climbing stairs', 'Osteoarthritis of knee', 'M17.9', ['Etoricoxib', 'Calcium + Vitamin D3', 'Diclofenac'], ['XKNEE', 'VITD']),
        ('Low back pain', 'Lumbago', 'M54.5', ['Naproxen', 'Tolperisone'], []),
        ('Neck pain radiating to arm', 'Cervical spondylosis', 'M47.8', ['Pregabalin', 'Etoricoxib', 'Vitamin B1+B6+B12'], []),
        ('Ankle swelling after fall', 'Ankle sprain', 'S93.4', ['Diclofenac', 'Paracetamol'], []),
        ('Shoulder stiffness', 'Adhesive capsulitis', 'M75.0', ['Naproxen', 'Tolperisone'], []),
        ('Joint pain, big toe swelling', 'Gout', 'M10.9', ['Naproxen'], ['URIC', 'CREAT']),
    ],
    'Dermatology': [
        ('Itchy circular rash', 'Tinea corporis', 'B35.4', ['Clotrimazole', 'Fluconazole', 'Cetirizine'], ['KOH']),
        ('Pimples on face', 'Acne vulgaris', 'L70.0', ['Isotretinoin'], ['ALT']),
        ('Intense itching at night', 'Scabies', 'B86', ['Permethrin', 'Cetirizine'], []),
        ('Dry itchy patches', 'Atopic dermatitis', 'L20.9', ['Betamethasone', 'Fexofenadine'], []),
        ('Red itchy wheals', 'Urticaria', 'L50.9', ['Fexofenadine', 'Montelukast'], ['CBC']),
    ],
    'Gynecology & Obstetrics': [
        ('Missed period, positive test', 'Routine antenatal care', 'Z34.9', ['Folic acid', 'Calcium + Vitamin D3', 'Iron + Folic acid + Zinc'], ['CBC', 'URE', 'USGWA']),
        ('Painful periods', 'Dysmenorrhoea', 'N94.6', ['Mefenamic acid'], ['USGWA']),
        ('Irregular cycles, weight gain', 'Polycystic ovary syndrome', 'E28.2', ['Metformin'], ['USGWA', 'FBS', 'TSH']),
        ('Nausea and vomiting in pregnancy', 'Hyperemesis gravidarum', 'O21.0', ['Ondansetron', 'Oral rehydration salts'], ['ELEC']),
        ('White discharge and itching', 'Vaginal candidiasis', 'B37.3', ['Fluconazole', 'Clotrimazole'], []),
    ],
    'ENT': [
        ('Blocked nose and sneezing', 'Allergic rhinitis', 'J30.4', ['Fluticasone furoate', 'Fexofenadine', 'Montelukast'], []),
        ('Facial pain and nasal discharge', 'Acute sinusitis', 'J01.9', ['Amoxicillin', 'Oxymetazoline', 'Paracetamol'], []),
        ('Ear discharge', 'Chronic otitis media', 'H66.3', ['Polymyxin + Neomycin + HC', 'Ciprofloxacin'], ['PTA']),
        ('Reduced hearing', 'Sensorineural hearing loss', 'H90.5', ['Vitamin B1+B6+B12'], ['PTA']),
        ('Sore throat, difficulty swallowing', 'Acute pharyngitis', 'J02.9', ['Azithromycin', 'Paracetamol'], []),
    ],
    'Neurology': [
        ('Recurrent one-sided headache', 'Migraine without aura', 'G43.0', ['Sumatriptan', 'Flunarizine'], []),
        ('Tension-type headache', 'Tension-type headache', 'G44.2', ['Paracetamol', 'Clonazepam'], []),
        ('Tingling in feet', 'Peripheral neuropathy', 'G62.9', ['Pregabalin', 'Vitamin B1+B6+B12'], ['FBS', 'HBA1C']),
        ('Seizure episode', 'Epilepsy', 'G40.9', ['Sodium valproate'], ['MRIB']),
        ('Weakness of one side (old)', 'Sequelae of stroke', 'I69.3', ['Aspirin', 'Atorvastatin'], ['MRIB', 'LIPID']),
    ],
    'Endocrinology': [
        ('Increased thirst and urination', 'Type 2 diabetes mellitus', 'E11.9', ['Metformin', 'Glimepiride'], ['FBS', 'HBA1C', 'CREAT']),
        ('Diabetes follow-up, poor control', 'Type 2 DM with hyperglycaemia', 'E11.65', ['Metformin', 'Linagliptin', 'Human insulin 30/70'], ['HBA1C', 'RBS', 'LIPID']),
        ('Weight gain and tiredness', 'Hypothyroidism', 'E03.9', ['Levothyroxine'], ['TSH', 'FT4']),
        ('Weight loss and tremor', 'Hyperthyroidism', 'E05.9', ['Carbimazole', 'Bisoprolol'], ['TSH', 'FT4']),
        ('Bone pain, low vitamin D', 'Vitamin D deficiency', 'E55.9', ['Cholecalciferol', 'Calcium + Vitamin D3'], ['VITD']),
    ],
}

FREQUENCIES = ['1+0+1', '1+1+1', '0+0+1', '1+0+0', '1+1+1+1', 'as needed']
INSTRUCTIONS = ['after meal', 'before meal', 'after meal', 'at bedtime', '', 'with plenty of water']
ADVICE = ['Drink plenty of fluids and take rest.', 'Avoid oily and spicy food.', 'Regular walking 30 minutes daily.',
          'Reduce salt intake.', 'Come back if symptoms worsen.', 'Avoid cold drinks and ice cream.',
          'Maintain sugar chart at home.', '']
CANCEL_REASONS = ['Patient requested reschedule', 'Doctor unavailable', '', '']

DEMO_PASSWORD = 'Clinic@2026'


def phone():
    return f'01{random.choice("3456789")}{random.randint(10_000_000, 99_999_999)}'


class Command(BaseCommand):
    help = 'Populate the clinic database with realistic demo data.'

    def add_arguments(self, parser):
        parser.add_argument('--patients', type=int, default=500)
        parser.add_argument('--appointments', type=int, default=3000)
        parser.add_argument('--days-back', type=int, default=365)
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--flush', action='store_true', help='Delete existing clinic data first')

    def handle(self, *args, **o):
        random.seed(o['seed'])
        if Patient.objects.exists() and not o['flush']:
            self.stdout.write(self.style.WARNING('Data already present. Use --flush to wipe and reseed.'))
            return
        with transaction.atomic():
            if o['flush']:
                self.flush()
            self.users()
            depts = self.departments()
            doctors = self.doctors(depts)
            meds = self.medicines()
            tests = self.lab_tests()
            patients = self.patients(o['patients'], o['days_back'])
            self.appointments(patients, doctors, meds, tests, o['appointments'], o['days_back'])
        self.summary()

    # ----------------------------------------------------------------------- helpers

    def flush(self):
        for m in [Payment, InvoiceItem, Invoice, LabOrder, PrescriptionItem, Prescription, Consultation,
                  Appointment, Patient, Doctor, Department, Medicine, LabTest]:
            m.objects.all().delete()
        User.objects.filter(username__startswith='dr.').delete()
        self.stdout.write('Flushed existing clinic data.')

    def users(self):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@clinic.local', DEMO_PASSWORD,
                                          first_name='System', last_name='Admin')
        reception, _ = Group.objects.get_or_create(name='Reception')
        reception.permissions.set(Permission.objects.filter(content_type__app_label='clinic'))
        doctors, _ = Group.objects.get_or_create(name='Doctors')
        doctors.permissions.set(Permission.objects.filter(content_type__app_label='clinic'))
        if not User.objects.filter(username='reception').exists():
            u = User.objects.create_user('reception', 'reception@clinic.local', DEMO_PASSWORD,
                                         first_name='Front', last_name='Desk', is_staff=True)
            u.groups.add(reception)
        self.doctor_group = doctors

    def departments(self):
        return {name: Department.objects.create(name=name, floor=f'{floor} floor', description=desc)
                for name, floor, desc in DEPARTMENTS}

    def doctors(self, depts):
        result, n = [], 0
        for dept_name, count in DOCTORS_PER_DEPT.items():
            spec, qual, fee = SPECIALIZATION[dept_name]
            for _ in range(count):
                n += 1
                female = random.random() < 0.4
                first = random.choice(FEMALE_FIRST if female else MALE_FIRST)
                last = random.choice(LAST_NAMES)
                start, end = random.choice(SHIFTS)
                username = f'dr.{first.lower()}{n}'
                user = User.objects.create_user(username, f'{username}@clinic.local', DEMO_PASSWORD,
                                                first_name=first, last_name=last, is_staff=True)
                user.groups.add(self.doctor_group)
                result.append(Doctor.objects.create(
                    user=user, first_name=first, last_name=last, department=depts[dept_name],
                    specialization=spec, qualification=qual, license_no=f'BMDC-A{random.randint(20000, 99999)}',
                    phone=phone(), email=f'{username}@clinic.local',
                    consultation_fee=Decimal(fee + random.choice([0, 0, 200, -100])),
                    available_days=random.choice(DAY_SETS), shift_start=start, shift_end=end,
                    is_active=random.random() > 0.05))
        return result

    def medicines(self):
        today = timezone.localdate()
        objs = []
        for name, generic, form, strength, mfr, price in MEDICINES:
            reorder = random.choice([50, 100, 200])
            stock = random.randint(0, reorder - 1) if random.random() < 0.12 else random.randint(reorder, reorder * 10)
            objs.append(Medicine(name=name, generic_name=generic, form=form, strength=strength, manufacturer=mfr,
                                 unit_price=Decimal(price), stock_quantity=stock, reorder_level=reorder,
                                 expiry_date=today + timedelta(days=random.randint(60, 900))))
        Medicine.objects.bulk_create(objs)
        by_generic = {}
        for m in Medicine.objects.all():
            by_generic.setdefault(m.generic_name, []).append(m)
        return by_generic

    def lab_tests(self):
        objs = []
        for name, code, cat, price, low, high, unit, dec in LAB_TESTS:
            rng = f'{low} – {high}' if low is not None else 'See report'
            objs.append(LabTest(name=name, code=code, category=cat, price=Decimal(price), normal_range=rng,
                                unit=unit, turnaround_hours=random.choice([4, 6, 24, 48])))
        LabTest.objects.bulk_create(objs)
        spec = {c: (low, high, dec) for _, c, _, _, low, high, _, dec in LAB_TESTS}
        return {t.code: (t, spec[t.code]) for t in LabTest.objects.all()}

    def patients(self, n, days_back):
        objs = []
        for i in range(1, n + 1):
            gender = random.choices(['M', 'F', 'O'], [48, 51, 1])[0]
            first = random.choice(FEMALE_FIRST if gender == 'F' else MALE_FIRST)
            last = random.choice(LAST_NAMES)
            age_days = int(random.triangular(180, 85 * 365, 32 * 365))
            area = random.choice(AREAS)
            ins = random.choice(INSURERS)
            objs.append(Patient(
                mrn=f'MRN{i:06d}', first_name=first, last_name=last,
                date_of_birth=timezone.localdate() - timedelta(days=age_days), gender=gender,
                blood_group=random.choices([g for g, _ in Patient.BLOOD_GROUPS], [30, 1, 27, 1, 8, 1, 31, 1])[0],
                phone=phone(),
                email=f'{first.lower()}.{last.lower()}{random.randint(1, 999)}@example.com' if random.random() < .6 else '',
                address=f'House {random.randint(1, 120)}, Road {random.randint(1, 30)}, {area}, Dhaka',
                emergency_contact_name=f'{random.choice(MALE_FIRST + FEMALE_FIRST)} {last}',
                emergency_contact_phone=phone(),
                allergies=random.choice(ALLERGIES),
                chronic_conditions=random.choice(CHRONIC) if age_days > 35 * 365 else '',
                insurance_provider=ins, insurance_number=f'POL{random.randint(100000, 999999)}' if ins else ''))
        Patient.objects.bulk_create(objs)
        return list(Patient.objects.all())

    def lab_result(self, code, spec):
        low, high, dec = spec
        abnormal = random.random() < 0.22
        if low is None:
            normal, abn = QUALITATIVE.get(code, (['Normal'], ['Abnormal']))
            return random.choice(abn if abnormal else normal), abnormal
        span = high - low
        if abnormal:
            value = random.choice([low - random.uniform(.05, .4) * span, high + random.uniform(.05, .8) * span])
            value = max(value, 0)
        else:
            value = random.uniform(low + span * .05, high - span * .05)
        return f'{value:.{dec}f}', abnormal

    def appointments(self, patients, doctors, meds, tests, n, days_back):
        tz = timezone.get_current_timezone()
        now = timezone.now()
        today = timezone.localdate()
        start_day = today - timedelta(days=days_back)
        end_day = today + timedelta(days=14)
        total_days = (end_day - start_day).days
        taken = set()
        active = [d for d in doctors if d.is_active]
        # each patient tends to stick with a few doctors
        loyal = {p.pk: random.sample(doctors, k=random.randint(1, 3)) for p in patients}
        weights = [random.paretovariate(1.5) for _ in patients]  # a few frequent visitors

        appts = []
        attempts = 0
        while len(appts) < n and attempts < n * 20:
            attempts += 1
            patient = random.choices(patients, weights)[0]
            doctor = random.choice(loyal[patient.pk]) if random.random() < .75 else random.choice(doctors)
            # more recent days are busier (clinic growth)
            day = start_day + timedelta(days=int(total_days * (random.random() ** 0.8)))
            days_ok = {WEEKDAY[d.strip()] for d in doctor.available_days.split(',') if d.strip() in WEEKDAY}
            if day.weekday() not in days_ok:
                continue
            if day > today and not doctor.is_active:
                doctor = random.choice(active)
            s, e = doctor.shift_start, doctor.shift_end
            slots = (e.hour * 60 + e.minute - s.hour * 60 - s.minute) // 15
            minute = s.hour * 60 + s.minute + 15 * random.randrange(max(slots, 1))
            when = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=tz)
            if (doctor.pk, when) in taken:
                continue
            taken.add((doctor.pk, when))

            if when < now - timedelta(hours=2):
                status = random.choices(['completed', 'cancelled', 'no_show'], [86, 8, 6])[0]
            elif when.date() == today:
                status = random.choices(['completed', 'checked_in', 'scheduled'], [3, 2, 5])[0] if when < now \
                    else 'scheduled'
            else:
                status = random.choices(['scheduled', 'cancelled'], [94, 6])[0]
            case = random.choice(CASES[doctor.department.name])
            visit = random.choices(['new', 'follow_up', 'emergency'], [55, 40, 5])[0]
            appts.append(Appointment(
                patient=patient, doctor=doctor, scheduled_at=when, duration_minutes=15, visit_type=visit,
                reason=case[0], status=status,
                notes=random.choice(CANCEL_REASONS) if status == 'cancelled' else ''))
            appts[-1]._case = case

        appts.sort(key=lambda a: a.scheduled_at)
        created = Appointment.objects.bulk_create(appts)
        for a, src in zip(created, appts):
            a._case = src._case
        self.stdout.write(f'  {len(created)} appointments')

        # backdate created_at so records look like they were entered at booking time
        for a in created:
            a.created_at = a.scheduled_at - timedelta(days=random.randint(0, 10), hours=random.randint(0, 8))
        Appointment.objects.bulk_update(created, ['created_at'], batch_size=500)

        first_visit = {}
        for a in created:
            first_visit.setdefault(a.patient_id, a.scheduled_at)
        for p in patients:
            fv = first_visit.get(p.pk, now - timedelta(days=random.randint(0, days_back)))
            p.created_at = min(fv, now) - timedelta(days=random.randint(0, 5), minutes=random.randint(5, 600))
        Patient.objects.bulk_update(patients, ['created_at'], batch_size=500)

        self.clinical_records([a for a in created if a.status in ('completed', 'checked_in')], meds, tests, now)

    def clinical_records(self, visits, meds, tests, now):
        consultations = []
        for a in visits:
            if a.status != 'completed':
                continue
            complaint, diagnosis, icd, _, _ = a._case
            p = a.patient
            adult = p.age >= 14
            hypertensive = 'Hypertension' in p.chronic_conditions or diagnosis.lower().find('hypert') >= 0
            sys_bp = random.randint(135, 170) if hypertensive else random.randint(100, 132)
            fever = 'fever' in complaint.lower() or 'fever' in diagnosis.lower()
            c = Consultation(
                appointment=a, chief_complaint=complaint, diagnosis=diagnosis, icd10_code=icd,
                symptoms=complaint + random.choice(['', ', mild nausea', ', poor appetite', ', disturbed sleep']),
                notes=random.choice(['', '', 'Patient counselled.', 'Review with reports.', 'Explained diagnosis.']),
                blood_pressure=f'{sys_bp}/{random.randint(65, 95 if hypertensive else 85)}',
                pulse=random.randint(62, 108), spo2=random.randint(94, 99),
                temperature=Decimal(str(round(random.uniform(100.2, 103.5) if fever else random.uniform(97.6, 99.0), 1))),
                weight_kg=Decimal(str(round(random.uniform(45, 92) if adult else random.uniform(6, 40), 1))),
                height_cm=Decimal(str(round(random.uniform(148, 182) if adult else random.uniform(65, 155), 1))),
                follow_up_date=(a.scheduled_at + timedelta(days=random.choice([7, 14, 30]))).date()
                if random.random() < .45 else None)
            c.created_at = a.scheduled_at + timedelta(minutes=random.randint(10, 25))
            consultations.append(c)
        consultations = Consultation.objects.bulk_create(consultations, batch_size=500)
        for c in consultations:
            c.created_at = c.appointment.scheduled_at + timedelta(minutes=random.randint(10, 25))
        Consultation.objects.bulk_update(consultations, ['created_at'], batch_size=500)
        self.stdout.write(f'  {len(consultations)} consultations')

        prescriptions = Prescription.objects.bulk_create(
            [Prescription(consultation=c, instructions=random.choice(ADVICE)) for c in consultations], batch_size=500)
        items, labs = [], []
        for c, rx in zip(consultations, prescriptions):
            _, _, _, generics, lab_codes = c.appointment._case
            for g in generics:
                options = meds.get(g)
                if not options:
                    continue
                med = random.choice(options)
                days = random.choice([3, 5, 7, 10, 14, 30])
                freq = random.choice(FREQUENCIES[:4]) if med.form in ('Tablet', 'Capsule') else random.choice(FREQUENCIES)
                per_day = max(1, freq.count('1')) if '+' in freq else 1
                qty = per_day * days if med.form in ('Tablet', 'Capsule') else 1
                items.append(PrescriptionItem(
                    prescription=rx, medicine=med,
                    dosage={'Tablet': '1 tablet', 'Capsule': '1 capsule', 'Syrup': '2 tsf', 'Inhaler': '2 puffs',
                            'Drops': '2 drops', 'Ointment': 'apply thinly', 'Injection': 'as directed'}[med.form],
                    frequency=freq, duration_days=days, quantity=qty, instructions=random.choice(INSTRUCTIONS)))
            for code in lab_codes:
                if random.random() < .25:  # not every test is ordered every time
                    continue
                test, spec = tests[code]
                ordered = c.appointment.scheduled_at + timedelta(minutes=random.randint(15, 40))
                done_at = ordered + timedelta(hours=test.turnaround_hours + random.randint(0, 6))
                if done_at < now:
                    status = random.choices(['completed', 'cancelled'], [96, 4])[0]
                else:
                    status = random.choice(['ordered', 'collected'])
                value, abnormal = self.lab_result(code, spec) if status == 'completed' else ('', False)
                labs.append(LabOrder(
                    patient=c.appointment.patient, consultation=c, ordered_by=c.appointment.doctor, test=test,
                    status=status, result_value=value, is_abnormal=abnormal, ordered_at=ordered,
                    completed_at=done_at if status == 'completed' else None,
                    result_notes='Please correlate clinically.' if abnormal else ''))
        PrescriptionItem.objects.bulk_create(items, batch_size=1000)
        LabOrder.objects.bulk_create(labs, batch_size=1000)
        self.stdout.write(f'  {len(items)} prescription items, {len(labs)} lab orders')
        self.billing(consultations, labs, now)

    def billing(self, consultations, labs, now):
        labs_by_c = {}
        for lo in labs:
            labs_by_c.setdefault(lo.consultation_id, []).append(lo)
        receptionist = User.objects.filter(username='reception').first()

        invoices, pending_items = [], []
        for i, c in enumerate(sorted(consultations, key=lambda c: c.appointment.scheduled_at), start=1):
            a = c.appointment
            issued = timezone.localtime(a.scheduled_at).date()
            lines = [('consultation', f'Consultation — {a.doctor}', 1, a.doctor.consultation_fee)]
            for lo in labs_by_c.get(c.pk, []):
                if lo.status != 'cancelled':
                    lines.append(('lab', lo.test.name, 1, lo.test.price))
            if random.random() < .1:
                lines.append(('procedure', random.choice(['Dressing', 'Nebulization', 'Injection push',
                                                          'Plaster application', 'Ear wax removal']),
                              1, Decimal(random.choice([200, 300, 500, 1500]))))
            subtotal = sum(q * p for _, _, q, p in lines)
            discount = (subtotal * Decimal(random.choice(['0.05', '0.10']))).quantize(Decimal('1')) \
                if random.random() < .12 else Decimal('0')
            invoices.append(Invoice(invoice_no=f'INV{i:07d}', patient=a.patient, appointment=a, issued_on=issued,
                                    due_on=issued + timedelta(days=14), discount=discount))
            pending_items.append((lines, subtotal - discount, a.scheduled_at))
        invoices = Invoice.objects.bulk_create(invoices, batch_size=500)

        items, payments = [], []
        for inv, (lines, total, when) in zip(invoices, pending_items):
            for kind, desc, qty, price in lines:
                items.append(InvoiceItem(invoice=inv, kind=kind, description=desc, quantity=qty, unit_price=price))
            age_days = (now - when).days
            roll = random.random()
            if roll < (.9 if age_days > 30 else .7):
                inv.status = 'paid'
                if random.random() < .15 and total > 1000:  # paid in two instalments
                    first = (total * Decimal('0.5')).quantize(Decimal('1'))
                    payments.append(self.payment(inv, first, when, receptionist))
                    payments.append(self.payment(inv, total - first, when + timedelta(days=random.randint(1, 10)),
                                                 receptionist))
                else:
                    payments.append(self.payment(inv, total, when + timedelta(minutes=random.randint(20, 90)),
                                                 receptionist))
            elif roll < .95:
                inv.status = 'partial'
                payments.append(self.payment(inv, (total * Decimal(random.choice(['0.3', '0.5', '0.6'])))
                                             .quantize(Decimal('1')), when + timedelta(minutes=40), receptionist))
            else:
                inv.status = 'unpaid'
        InvoiceItem.objects.bulk_create(items, batch_size=1000)
        payments = [p for p in payments if p.paid_at <= now]
        Payment.objects.bulk_create(payments, batch_size=1000)
        Invoice.objects.bulk_update(invoices, ['status'], batch_size=500)
        # payments scheduled "in the future" were dropped above → fix those statuses
        for inv in Invoice.objects.filter(status='paid', payments__isnull=True):
            inv.status = 'unpaid'
            inv.save(update_fields=['status'])
        for inv in Invoice.objects.filter(status='paid').prefetch_related('items', 'payments'):
            if inv.balance > 0:
                inv.refresh_status()
        self.stdout.write(f'  {len(invoices)} invoices, {len(payments)} payments')

    @staticmethod
    def payment(inv, amount, when, user):
        method = random.choices(['cash', 'card', 'mobile', 'insurance'], [45, 20, 30, 5])[0]
        ref = {'card': f'CARD-{random.randint(1000, 9999)}', 'mobile': f'TXN{random.randint(10**9, 10**10 - 1)}',
               'insurance': f'CLM-{random.randint(10000, 99999)}'}.get(method, '')
        return Payment(invoice=inv, amount=amount, method=method, reference=ref, paid_at=when, received_by=user)

    def summary(self):
        self.stdout.write(self.style.SUCCESS('Database seeded:'))
        for m in [Department, Doctor, Patient, Appointment, Consultation, Prescription, PrescriptionItem, Medicine,
                  LabTest, LabOrder, Invoice, InvoiceItem, Payment]:
            self.stdout.write(f'  {m._meta.verbose_name_plural.title():<22} {m.objects.count():>6}')
        self.stdout.write(f'Login users: admin, reception, and one dr.* account per doctor (see README.md).')
