"""
The 20-Patient Benchmark Cohort.
Encompasses pediatric, adult, geriatric, zero-history, and subtle clinical presentations.
"""

from typing import List
from triage.models import PatientRecord, Vitals

BENCHMARK_COHORT: List[PatientRecord] = [
    # 1. Pediatric PEWS vital red-line
    PatientRecord(
        id="P-001", name="Baby Leo",
        vitals=Vitals(age=0.33, heart_rate=188, systolic_bp=82, diastolic_bp=50, resp_rate=54, spo2=96.0, temp_celsius=38.9, pain_scale=6),
        chief_complaint="High fever, extreme lethargy, and poor feeding over 24 hours.",
        history=[],
    ),
    # 2. Geriatric atypical silent MI (ACS)
    PatientRecord(
        id="P-002", name="Eleanor Vance",
        vitals=Vitals(age=78.0, heart_rate=102, systolic_bp=104, diastolic_bp=65, resp_rate=18, spo2=95.0, temp_celsius=36.1, pain_scale=3),
        chief_complaint="Severe indigestion, epigastric discomfort, and profound fatigue.",
        history=["Type 2 Diabetes Mellitus", "Dyslipidemia"],
    ),
    # 3. Zero-history baseline; triggers VOI
    PatientRecord(
        id="P-003", name="Marcus Reed",
        vitals=Vitals(age=34.0, heart_rate=86, systolic_bp=138, diastolic_bp=88, resp_rate=16, spo2=99.0, temp_celsius=37.1, pain_scale=8),
        chief_complaint="Severe mid-epigastric pain radiating to back.",
        history=[],
    ),
    # 4. Ambiguous stroke mimic -> VOI FAST
    PatientRecord(
        id="P-004", name="David Miller",
        vitals=Vitals(age=67.0, heart_rate=74, systolic_bp=168, diastolic_bp=96, resp_rate=16, spo2=98.0, temp_celsius=36.8, pain_scale=1),
        chief_complaint="Sudden mild dizziness and left facial numbness.",
        history=["Hypertension"],
    ),
    # 5. Pediatric airway compromise
    PatientRecord(
        id="P-005", name="Chloe Bennett",
        vitals=Vitals(age=6.0, heart_rate=142, systolic_bp=94, diastolic_bp=60, resp_rate=38, spo2=92.0, temp_celsius=37.8, pain_scale=5),
        chief_complaint="Barking cough and inspiratory stridor at rest.",
        history=["Asthma"],
    ),
    # 6. Occult geriatric sepsis (Hypothermia)
    PatientRecord(
        id="P-006", name="Frank Robinson",
        vitals=Vitals(age=82.0, heart_rate=110, systolic_bp=86, diastolic_bp=52, resp_rate=24, spo2=93.0, temp_celsius=35.2, pain_scale=2),
        chief_complaint="Shivering and acute mild confusion.",
        history=["Dementia", "Prostatic Hyperplasia"],
    ),
    # 7. Musculoskeletal vs Pleuritic check
    PatientRecord(
        id="P-007", name="Jamal Walker",
        vitals=Vitals(age=28.0, heart_rate=88, systolic_bp=122, diastolic_bp=78, resp_rate=18, spo2=99.0, temp_celsius=36.6, pain_scale=5),
        chief_complaint="Sudden sharp chest pain after heavy deadlifting.",
        history=[],
    ),
    # 8. Acute appendicitis resource triage
    PatientRecord(
        id="P-008", name="Maria Santos",
        vitals=Vitals(age=45.0, heart_rate=94, systolic_bp=125, diastolic_bp=80, resp_rate=18, spo2=98.0, temp_celsius=38.0, pain_scale=7),
        chief_complaint="Migrating RLQ abdominal pain and nausea.",
        history=[],
    ),
    # 9. Fast-Track candidate under surge
    PatientRecord(
        id="P-009", name="Sam Chen",
        vitals=Vitals(age=19.0, heart_rate=72, systolic_bp=118, diastolic_bp=74, resp_rate=14, spo2=100.0, temp_celsius=36.7, pain_scale=4),
        chief_complaint="Inverted right ankle while running, able to bear weight.",
        history=[],
    ),
    # 10. High-risk medication alert (Warfarin fall)
    PatientRecord(
        id="P-010", name="Arthur Pendelton",
        vitals=Vitals(age=72.0, heart_rate=72, systolic_bp=135, diastolic_bp=80, resp_rate=14, spo2=98.0, temp_celsius=36.7, pain_scale=2),
        chief_complaint="Ground-level mechanical fall, bumped forehead.",
        history=["Atrial Fibrillation", "Warfarin anticoagulation"],
    ),
    # 11. SVT vs Panic query
    PatientRecord(
        id="P-011", name="Priya Patel",
        vitals=Vitals(age=29.0, heart_rate=138, systolic_bp=132, diastolic_bp=84, resp_rate=22, spo2=100.0, temp_celsius=36.7, pain_scale=3),
        chief_complaint="Rapid heart palpitations and tingling fingers.",
        history=[],
    ),
    # 12. Low-acuity non-urgent control
    PatientRecord(
        id="P-012", name="Liam Johnson",
        vitals=Vitals(age=8.0, heart_rate=88, systolic_bp=100, diastolic_bp=65, resp_rate=20, spo2=99.0, temp_celsius=36.8, pain_scale=2),
        chief_complaint="Superficial bicycle handlebar scrape on forearm.",
        history=[],
    ),
    # 13. DVT / Pulmonary embolism risk
    PatientRecord(
        id="P-013", name="Brenda Taylor",
        vitals=Vitals(age=58.0, heart_rate=98, systolic_bp=128, diastolic_bp=82, resp_rate=22, spo2=94.0, temp_celsius=36.9, pain_scale=6),
        chief_complaint="Left calf aching, swelling, and slight breathlessness after a 12-hour flight.",
        history=["Hormone Replacement Therapy"],
    ),
    # 14. Rupturing AAA / Vascular catastrophe
    PatientRecord(
        id="P-014", name="Kenneth Wright",
        vitals=Vitals(age=61.0, heart_rate=114, systolic_bp=84, diastolic_bp=48, resp_rate=26, spo2=94.0, temp_celsius=36.2, pain_scale=10),
        chief_complaint="Sudden tearing mid-back pain with syncope episode.",
        history=["Hypertension", "Smoking (40 pack-years)"],
    ),
    # 15. Airway threat (Peritonsillar)
    PatientRecord(
        id="P-015", name="Zoe Adams",
        vitals=Vitals(age=22.0, heart_rate=106, systolic_bp=118, diastolic_bp=74, resp_rate=18, spo2=97.0, temp_celsius=38.8, pain_scale=9),
        chief_complaint="Severe sore throat, muffled voice, and drooling.",
        history=[],
    ),
    # 16. Minimal resource utilization (Suture removal)
    PatientRecord(
        id="P-016", name="Robert King",
        vitals=Vitals(age=50.0, heart_rate=68, systolic_bp=124, diastolic_bp=78, resp_rate=14, spo2=99.0, temp_celsius=36.6, pain_scale=0),
        chief_complaint="Routine suture removal from laceration 10 days ago.",
        history=["None"],
    ),
    # 17. Zero-history geriatric decline
    PatientRecord(
        id="P-017", name="Evelyn Scott",
        vitals=Vitals(age=88.0, heart_rate=60, systolic_bp=108, diastolic_bp=68, resp_rate=16, spo2=95.0, temp_celsius=36.0, pain_scale=1),
        chief_complaint="General debility and weakness over 4 days with low oral intake.",
        history=[],
    ),
    # 18. Acute meningitis red flag
    PatientRecord(
        id="P-018", name="Carlos Gomez",
        vitals=Vitals(age=38.0, heart_rate=118, systolic_bp=130, diastolic_bp=85, resp_rate=20, spo2=97.0, temp_celsius=39.4, pain_scale=9),
        chief_complaint="Violent headache, photophobia, and severe neck stiffness.",
        history=[],
    ),
    # 19. Hypoxemic adolescent asthma exacerbation
    PatientRecord(
        id="P-019", name="Hannah Mitchell",
        vitals=Vitals(age=16.0, heart_rate=126, systolic_bp=115, diastolic_bp=70, resp_rate=32, spo2=90.0, temp_celsius=37.0, pain_scale=6),
        chief_complaint="Severe asthma flare, speaking in 2-word dyspneic bursts.",
        history=["Severe Persistent Asthma"],
    ),
    # 20. Non-anaphylactic allergic reaction
    PatientRecord(
        id="P-020", name="Tom Bradley",
        vitals=Vitals(age=42.0, heart_rate=82, systolic_bp=124, diastolic_bp=80, resp_rate=16, spo2=99.0, temp_celsius=36.8, pain_scale=3),
        chief_complaint="Generalized itchy hives after taking Amoxicillin, airway completely clear.",
        history=["Penicillin Allergy (new)"],
    ),
]


def load_benchmark_cohort() -> List[PatientRecord]:
    """Returns a fresh deep copy of the benchmark cohort."""
    return [p.model_copy(deep=True) for p in BENCHMARK_COHORT]