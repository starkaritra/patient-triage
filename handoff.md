# PatientTriage.ai — Master Blueprint & Engineering Handoff

**Project:** PatientTriage.ai  
**Phase:** Round 2 Prototype & Clinical Architecture  
**Target Delivery:** Swappable Algorithmic/ML Core with Dynamic Deterioration Radar, Active VOI Assistant, and Streamlit Clinical HUD.

---

## 1. Executive Summary & North-Star Goal

### 1.1 Objective
Build an explainable, safety-biased clinical decision-support triage system that:
1. Assesses incoming emergency department (ED) patients across all age brackets (**Pediatric, Adult, Geriatric**).
2. Generates standard 5-level **Emergency Severity Index (ESI 1 to 5)** acuity recommendations with a calibrated **Confidence Metric (0–100%)**.
3. Detects ambiguous presentations and dynamically triggers **Value of Information (VOI)** follow-up questions to collapse diagnostic uncertainty.
4. Continuously monitors the waiting room for **clinical deterioration** (time-in-queue decay and worsening vitals).
5. Adapts to **Surge Conditions (3× normal load)** by prioritizing deteriorating high-acuity patients and auto-routing stable ESI 4/5 cases to Fast-Track lanes.
6. Guarantees clinical accountability through **1-click clinician overrides** and an immutable audit logging pipeline aligned with US HIPAA / ONC CDS and EU MDR standards.

### 1.2 Core Architectural Principle: Swappable Decision Core
The system is built on an abstract interface (`BaseTriageEngine`). 
- **Round 2 Baseline:** Fully deterministic physiological red-lines + statistical/heuristic scoring model + rule-indexed VOI question bank (runs locally, zero API dependency, < 50 ms latency).
- **Future Extension:** Pluggable Fine-Tuned LLM or RAG differential agent by implementing a single adapter class without touching the UI, queue, or audit layers.

---

## 2. Problem Statement & Clinical Realities

### 2.1 Real-World Complexities to Consider
- **Overlapping & Ambiguous Presentations:** Patients present with overlapping or ambiguous symptoms that don't map cleanly onto standard severity scales — some patients under-report pain or symptoms, and presentation can differ significantly by age or condition.
- **Population-Specific Physiological Thresholds:** Vital sign thresholds and symptom weights differ significantly across pediatric, adult, and geriatric populations — a fever of 38.5°C carries different clinical urgency in a 3-year-old versus a 75-year-old. Solutions that apply a single adult-calibrated scoring model across all age groups introduce silent safety risk.
- **Variable Intake Data Availability:** Data quality and availability at intake varies hugely — a returning patient may have a rich history in the hospital's systems, while a first-time patient may have almost nothing beyond what's observed in the moment.
- **High Cognitive Load & Sub-Second Latency Demands:** Triage decisions must be made — and be explainable — within seconds, by a clinician who is often simultaneously managing several other patients.
- **Asymmetric Cost of Error:** Under-triage and over-triage carry asymmetric costs — missing a critical case is categorically worse than over-prioritizing a minor one. Any solution must be deliberately tuned to bias toward escalation under uncertainty rather than optimized for average accuracy, and teams must demonstrate this design choice explicitly in their prototype.
- **Hospital Heterogeneity:** Hospitals differ enormously in scale, specialty mix, and staffing — a workflow that works for a large urban trauma center may not transfer to a small rural emergency department.
- **Clinical Accountability & Legal Liability:** Clinical accountability and liability mean any recommendation must remain reviewable and overridable by a licensed clinician, with a clear audit trail and compliance with health-data regulation.
- **Integration Friction:** Integration with existing hospital systems (patient records, bed management, staff rosters) is rarely simple, and system maturity varies a great deal from one hospital to the next.

### 2.2 Solutioning Areas Explored
- **Data Strategy:** How we structure and weigh available inputs (vitals, self-reported symptoms, history, observed cues) despite inconsistent completeness.
- **Decision Model:** Rules-based scoring, ML-based risk scoring, or a hybrid, and how we represent the assistant's own epistemic uncertainty.
- **Workflow Design:** How a recommendation is surfaced to a nurse in the moment, how overrides are captured, and how the system behaves differently during a surge versus a quiet shift.
- **Safety-First Design:** Sensible fail-safe defaults (for example, escalating rather than downgrading when uncertain), and ongoing monitoring of waiting patients for signs of deterioration. The system must monitor patients already in the waiting queue and trigger re-assessment if wait time exceeds safe thresholds for their severity level or if vitals are re-recorded as worsening.
- **Adoption & Change Management:** How to get fatigued, time-pressured staff to actually trust and use the tool rather than work around it.
- **Patient Data Protection:** How patient data is protected from unfair and unauthorized usage (zero third-party leak, local compute option).
- **Scalability:** How the same underlying assistant can flex across hospitals of very different size, specialty mix, and technical maturity.

### 2.3 Reference Parameters (Illustrative & Directional)
- **ED Volume:** Designed for emergency departments ranging from roughly 100 to 500+ patient visits per day.
- **Triage Standard:** Standard 5-level severity scale (**Emergency Severity Index: ESI 1 to 5**).
- **Data Completeness:** Handles mixed data availability — roughly half of arriving patients have prior health records on file, and half are zero-history walk-ins.
- **Regulatory Jurisdiction:** Formatted for US HIPAA / ONC CDS compliance and EU MDR Annex VIII Rule 11 standards (governing audit trail durability, data retention policies, consent boundaries, and mandatory clinician override justifications).

---

## 3. Clinical Framework & Safety Design

```
+---------------------------------------------------------------------------------------------------+
|                                 PHYSIOLOGICAL SEVERITY SPECTRUM                                   |
+---------------------------------------------------------------------------------------------------+
|  ESI 1: Resuscitation  | Immediate life threat (Cardiac arrest, severe airway failure)             |
|  ESI 2: Emergent       | High-risk presentation, vitals near red-line, severe pain/confusion      |
|  ESI 3: Urgent         | Stable vitals, requires 2+ hospital resources (Labs, IV, CT scan)        |
|  ESI 4: Less Urgent    | Stable vitals, requires 1 resource (X-ray, simple suture, oral meds)     |
|  ESI 5: Non-Urgent     | Stable vitals, requires 0 resources (Prescription refill, exam only)     |
+---------------------------------------------------------------------------------------------------+
```

### 3.1 Age-Stratified Vital Thresholds (PEWS & NEWS2 Calibrated)
Thresholds are dynamically selected based on `age_category`:

| Vital Parameter | Infant (<1 yr) | Child (1–12 yrs) | Adult (13–64 yrs) | Geriatric (65+ yrs) |
| :--- | :--- | :--- | :--- | :--- |
| **Heart Rate (HR)** | Normal: 100–160<br>Critical: >180 / <80 | Normal: 70–120<br>Critical: >140 / <60 | Normal: 60–100<br>Critical: >120 / <50 | Normal: 60–90<br>Critical: >105 / <50 |
| **Respiratory (RR)** | Normal: 30–50<br>Critical: >60 / <20 | Normal: 18–30<br>Critical: >40 / <14 | Normal: 12–20<br>Critical: >28 / <10 | Normal: 12–20<br>Critical: >26 / <10 |
| **Systolic BP (SBP)**| Normal: 70–100<br>Critical: <70 | Normal: 85–115<br>Critical: <80 | Normal: 100–140<br>Critical: <90 / >190 | Normal: 110–145<br>Critical: <95 / >190 |
| **Temperature** | Fever: >38.0°C<br>Critical: ≥38.5°C | Fever: >38.3°C<br>Critical: ≥39.0°C | Fever: >38.3°C<br>Critical: ≥39.5°C | Hypothermia: <35.5°C<br>Fever: >37.8°C |
| **SpO<sub>2</sub>** | Critical: <94% | Critical: <93% | Critical: <92% | Critical: <91% |

### 3.2 Asymmetric Clinical Loss Function
Missing a critical case (**under-triage**) is 10× worse than over-prioritizing a stable patient (**over-triage**):

```math
\text{Loss}(\text{True ESI } 1/2 \to \text{Assigned ESI } 3/4) \gg \text{Loss}(\text{True ESI } 4 \to \text{Assigned ESI } 3)
```

- **Rule:** If epistemic confidence is low (< 70%) on any high-risk symptom, the engine defaults to **escalating urgency by +1 tier** rather than defaulting to average acuity.

---

## 4. System Architecture & Module Contracts

```
patient-triage/
├── triage/
│   ├── __init__.py
│   ├── models.py         # Data schemas (PatientRecord, Vitals, TriageResult)
│   ├── engine.py         # BaseTriageEngine & AlgorithmicTriageEngine
│   ├── rules.py          # Deterministic physiological red-lines (PEWS/NEWS2)
│   ├── voi.py            # Active Question Generator (Value-of-Information)
│   ├── queue.py          # Dynamic Queue, Deterioration Tracker & Surge Engine
│   ├── audit.py          # Immutable JSON Audit & Override Logger
│   └── cohort.py         # 20 Simulated Patient Records Bench
├── app.py                # Interactive Streamlit Clinical Dashboard
├── requirements.txt      # Lightweight dependencies (streamlit, pandas, pydantic)
└── README.md             # Quickstart & Verification Instructions
```

### 4.1 Data Models (`triage/models.py`)

```python
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class AgeCategory(str, Enum):
    INFANT = "infant"
    CHILD = "child"
    ADULT = "adult"
    GERIATRIC = "geriatric"

class Vitals(BaseModel):
    age: float
    heart_rate: int
    systolic_bp: int
    diastolic_bp: int
    resp_rate: int
    spo2: float
    temp_celsius: float
    pain_scale: int

class PatientRecord(BaseModel):
    id: str
    name: str
    vitals: Vitals
    chief_complaint: str
    history: List[str] = []
    wait_time_minutes: int = 0
    assigned_esi: Optional[int] = None
    override_esi: Optional[int] = None
    override_reason: Optional[str] = None
    answers_to_followups: Dict[str, str] = {}

class TriageResult(BaseModel):
    esi_level: int
    confidence: float
    primary_risk_factors: List[str]
    is_ambiguous: bool
    recommended_followups: List[str]
    deterministic_rule_hit: bool
    explanation: List[str]
```

### 4.2 Swappable Engine Contract (`triage/engine.py`)

```python
from abc import ABC, abstractmethod
from triage.models import PatientRecord, TriageResult

class BaseTriageEngine(ABC):
    @abstractmethod
    def evaluate(self, patient: PatientRecord) -> TriageResult:
        """Evaluates patient and returns standardized TriageResult."""
        pass

class AlgorithmicTriageEngine(BaseTriageEngine):
    """
    Deterministic safety-gate + rule-weighted clinical risk baseline.
    Zero external dependencies, sub-millisecond execution.
    """
    def evaluate(self, patient: PatientRecord) -> TriageResult:
        # Step 1: Run deterministic physiological red-lines (PEWS/NEWS2)
        # Step 2: Calculate symptom risk weight & resource needs
        # Step 3: Compute confidence & ambiguity index
        # Step 4: Generate VOI questions if confidence < 0.70
        pass
```

---

## 5. Confidence Metric & Active VOI Question Engine

### 5.1 Confidence Score Formula
Confidence is derived from 4 penalized dimensions:

```math
\text{Confidence} = 1.0 - P_{\text{data}} - P_{\text{vitals}} - P_{\text{ambiguity}} - P_{\text{age\_risk}}
```

1. **Missing History Penalty (P<sub>data</sub>):** 0.15 if `len(patient.history) == 0` (Zero-history patient).
2. **Vital Variance Penalty (P<sub>vitals</sub>):** 0.10 if vitals lie in borderline gray zones (e.g., HR 98–105 in adult).
3. **Symptom Ambiguity Penalty (P<sub>ambiguity</sub>):** 0.20 if complaint matches high-entropy differential sets (e.g., "Dizziness", "Fatigue", "Epigastric discomfort").
4. **Age Risk Penalty (P<sub>age_risk</sub>):** 0.10 for infants (< 1 yr) or geriatric patients (> 75 yrs) presenting with non-specific systemic symptoms.

### 5.2 VOI (Value of Information) Question Mapping
When Confidence < 0.70, `triage/voi.py` triggers targeted clinical checks:

| Presenting Symptom / Category | Trigger Condition | High-Yield VOI Follow-Up Question | Impact on Re-assessment |
| :--- | :--- | :--- | :--- |
| **Epigastric Pain / Indigestion** | Adult/Geriatric, Diabetic or Female | *"Is there associated diaphoresis, nausea, or radiation to jaw/arm?"* | If Yes → Escalates to **ESI 2** (Atypical ACS). |
| **Vague Dizziness / Imbalance** | Geriatric or Hypertensive | *"Are there unilateral facial droop, arm drift, or speech changes (FAST)?"* | If Yes → Escalates to **ESI 2** (Stroke Alert). |
| **Calf Pain / Swelling** | Female on OCP or Recent Immobility | *"Is there unilateral leg swelling or shortness of breath on exertion?"* | If Yes → Escalates to **ESI 2** (DVT/PE risk). |
| **High Fever** | Infant (< 1 yr) | *"Is the infant making wet diapers and making eye contact?"* | If No → Escalates to **ESI 2** (Decompensated sepsis). |
| **Palpitations & Paresthesia** | Young adult, SpO2 100% | *"Is there lightheadedness, chest pressure, or history of SVT?"* | If Yes → ESI 2/3 (ECG check); If No → ESI 4 (Panic check). |

---

## 6. Dynamic Queue Deterioration & 3× Surge Engine

### 6.1 Safe Wait Time Windows & Auto-Retriage Trigger
Each ESI tier has a strict maximum safe waiting threshold:
- **ESI 1:** 0 min (Immediate Bedding)
- **ESI 2:** 10 min max wait
- **ESI 3:** 30 min max wait
- **ESI 4:** 60 min max wait
- **ESI 5:** 120 min max wait

**Deterioration Score Formula:**

```math
\text{Priority Score} = (6 - \text{ESI}) \times 100 + \left(\frac{\text{Wait Time}}{\text{Safe Threshold}}\right) \times 50 + \Delta \text{Vitals Penalty}
```

- If Wait Time > Safe Threshold, the UI highlights the patient in **flashing amber/red** with a `"RE-TRIAGE REQUIRED"` alert.
- If nurse inputs updated vitals showing decompensation (e.g., SBP drops from 115 → 92), the patient jumps to the top of the queue.

### 6.2 3× Surge Adaptation Mode
When the charge nurse toggles **Surge Mode**:
1. **Queue Re-balancing:** Patients are ranked by composite deterioration risk rather than arrival timestamp.
2. **Fast-Track Diversion:** Stable ESI 4 and ESI 5 patients are visually segregated into a separate "Fast-Track / Minor Injury Unit" queue to prevent ED bed blocking.
3. **Bottleneck Transparency:** Displays live telemetry: Beds Occupied, Waiting Room Count, Average Time-to-Doctor, and Re-Triage Alert Count.

---

## 7. Clinician Review & Immutable Audit Trail

### 7.1 Regulatory Compliance Guarantee (HIPAA / EU MDR / ONC CDS)
- AI recommendations are strictly advisory and never autonomously commit medical records.
- All assessments, nurse acceptances, and manual overrides are recorded in an append-only audit ledger (`audit_log.json`).

### 7.2 Audit Schema (`triage/audit.py`)
```json
{
  "timestamp": "2026-08-29T21:40:00Z",
  "patient_id": "P-002",
  "patient_name": "Eleanor Vance (78 yo)",
  "ai_recommendation": {
    "esi_level": 2,
    "confidence": 0.65,
    "deterministic_hit": false,
    "primary_risk_factors": ["Diabetic", "Atypical epigastric pain/fatigue", "Geriatric ACS risk"]
  },
  "voi_interaction": {
    "question_asked": "Is there associated diaphoresis, nausea, or arm/jaw discomfort?",
    "answer_received": "Yes, mild cold sweats and jaw heaviness"
  },
  "clinician_decision": {
    "final_esi": 2,
    "was_overridden": false,
    "clinician_id": "RN-4402",
    "override_reason": null
  }
}
```

---

## 8. The 20-Patient Benchmark Cohort (`triage/cohort.py`)

| # | ID | Name & Age | Presentation & History | Vitals | Expected ESI & Conf | Test Objective |
|---|---|---|---|---|---|---|
| **1** | `P-001` | Baby Leo (4 mo) | High fever, lethargy, poor feeding. Zero history. | T: 38.9°C, HR: 188, RR: 54, SpO2: 96% | **ESI 2** (92% Conf) | Pediatric PEWS vital red-line. |
| **2** | `P-002` | Eleanor (78 yo F) | "Indigestion" and profound fatigue. Hx: Type 2 Diabetes. | T: 36.1°C, HR: 102, BP: 104/65, SpO2: 95% | **ESI 2** (65% → 85% post-VOI) | Geriatric atypical silent MI (ACS). |
| **3** | `P-003` | Marcus (34 yo M) | Severe mid-epigastric pain. Zero prior history. | T: 37.1°C, HR: 86, BP: 138/88, SpO2: 99% | **ESI 3** (55% Conf) | Zero-history baseline; triggers VOI. |
| **4** | `P-004` | David (67 yo M) | Sudden mild dizziness & left facial numbness. Hx: HTN. | T: 36.8°C, HR: 74, BP: 168/96, SpO2: 98% | **ESI 2** (60% Conf) | Ambiguous stroke mimic → VOI FAST. |
| **5** | `P-005` | Chloe (6 yo F) | Barking cough, inspiratory stridor at rest. Hx: Asthma. | T: 37.8°C, HR: 142, RR: 38, SpO2: 92% | **ESI 2** (90% Conf) | Pediatric airway compromise. |
| **6** | `P-006` | Frank (82 yo M) | Shivering, mild confusion. Hx: Dementia. | T: 35.2°C (Hypothermic), HR: 110, BP: 86/52 | **ESI 2** (95% Conf) | Occult geriatric sepsis (qSOFA red-line). |
| **7** | `P-007` | Jamal (28 yo M) | Sudden sharp chest pain after heavy deadlifting. | T: 36.6°C, HR: 88, BP: 122/78, SpO2: 99% | **ESI 3** (70% Conf) | Musculoskeletal vs Pleuritic check. |
| **8** | `P-008` | Maria (45 yo F) | Migrating RLQ abdominal pain, nausea. Hx: None. | T: 38.0°C, HR: 94, BP: 125/80, SpO2: 98% | **ESI 3** (80% Conf) | Acute appendicitis resource triage. |
| **9** | `P-009` | Sam (19 yo NB) | Inverted right ankle while running, bearing weight. | Vitals completely normal. Pain: 4/10. | **ESI 4** (95% Conf) | Fast-Track candidate under surge. |
| **10**| `P-010` | Arthur (72 yo M) | Ground-level mechanical fall, on Warfarin. Normal vitals. | T: 36.7°C, HR: 72, BP: 135/80, SpO2: 98% | **ESI 2** (85% Conf) | High-risk medication alert (Intracranial bleed). |
| **11**| `P-011` | Priya (29 yo F) | Rapid palpitations & tingling fingers. Zero history. | T: 36.7°C, HR: 138, BP: 132/84, SpO2: 100% | **ESI 3** (58% Conf) | SVT vs Panic attack → VOI ECG query. |
| **12**| `P-012` | Liam (8 yo M) | Superficial bicycle handlebar scrape. | Vitals normal. Pain: 2/10. | **ESI 5** (98% Conf) | Low-acuity non-urgent control. |
| **13**| `P-013` | Brenda (58 yo F) | Left calf aching & slight breathlessness. Recent flight. | T: 36.9°C, HR: 98, BP: 128/82, SpO2: 94% | **ESI 2** (62% Conf) | DVT / Pulmonary embolism risk. |
| **14**| `P-014` | Kenneth (61 yo M) | Sudden tearing back pain, syncope. Hx: HTN. | T: 36.2°C, HR: 114, BP: 84/48, SpO2: 94% | **ESI 1/2** (98% Conf) | Rupturing AAA / Hemorrhagic shock. |
| **15**| `P-015` | Zoe (22 yo F) | Severe sore throat, muffled voice, drooling. | T: 38.8°C, HR: 106, BP: 118/74, SpO2: 97% | **ESI 2** (90% Conf) | Airway threat (Peritonsillar abscess). |
| **16**| `P-016` | Robert (50 yo M) | Routine suture removal from laceration 10 days ago. | Vitals completely normal. | **ESI 5** (99% Conf) | Minimal resource utilization. |
| **17**| `P-017` | Evelyn (88 yo F) | General debility over 4 days, low intake. Zero records. | T: 36.0°C, HR: 60, BP: 108/68, SpO2: 95% | **ESI 3** (52% Conf) | Zero-history geriatric decline → VOI check. |
| **18**| `P-018` | Carlos (38 yo M) | Violent headache, photophobia, neck stiffness. | T: 39.4°C, HR: 118, BP: 130/85, SpO2: 97% | **ESI 2** (95% Conf) | Acute meningitis red flag. |
| **19**| `P-019` | Hannah (16 yo F) | Severe asthma flare, 2-word dyspnea. Hx: Asthma. | T: 37.0°C, HR: 126, RR: 32, SpO2: 90% | **ESI 2** (96% Conf) | Hypoxemic adolescent asthma exacerbation. |
| **20**| `P-020` | Tom (42 yo M) | Generalized hives after Amoxicillin, airway clear. | T: 36.8°C, HR: 82, BP: 124/80, SpO2: 99% | **ESI 4** (88% Conf) | Non-anaphylactic allergic reaction. |

---

## 9. Clinical Dashboard UI Specification (`app.py`)

The Streamlit UI is organized into 3 clear clinical workstations:

```
+---------------------------------------------------------------------------------------------------+
|  PATIENTTRIAGE.AI  |  STATUS: ONLINE  |  ED OCCUPANCY: 94%  |  [ TOGGLE 3X SURGE MODE ]           |
+---------------------------------------------------------------------------------------------------+
|  [TAB 1: INTAKE & SCORER]   |   [TAB 2: WAITING ROOM RADAR]   |   [TAB 3: AUDIT & OVERRIDE LOG]   |
+-----------------------------+---------------------------------+-----------------------------------+
| Patient Selector / Manual:  | Live Deterioration Queue:       | Immutable Event Stream:           |
| - Name, Age, Category       | - Patient P-006 (Waited 35m)    | - 21:40: P-002 Assessed -> ESI 2  |
| - Vitals Input Sliders      |   [! RETRIAGE BREACH !]         | - 21:42: RN-4402 Overrode P-003   |
| - Complaint & History Check | - Patient P-002 (Waited 12m)    |   Reason: "Observed severe pallor"|
|                             |                                 |                                   |
| AI Recommendation Card:     | Fast-Track Diversion Queue:     | Export Actions:                   |
| - ESI Level Gauge (1 - 5)   | - Patient P-009 (Ankle sprain)  | [ Download JSON Audit Log ]       |
| - Confidence: [ 65% (MED) ] | - Patient P-016 (Suture removal)| [ Reset Simulation ]              |
|                             |                                 |                                   |
| Active VOI Question Box:    | Time Simulation Triggers:       |                                   |
| "Diabetic female with fatigue"| [ +15 min Wait ] [ Vitals Drop] |                                   |
| [Ask: Diaphoresis/Jaw pain?]|                                 |                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 10. Future Horizon (v2) Strategic Architecture

### 10.1 The Four Architectural Pillars
1. **Pillar 1: FHIR v4 Clinical Ingestion Gateway:** Embedded FastAPI listener (`/Observation`, `/Patient`, `/Encounter`) accepting direct JSON bundles from bedside vital monitors and hospital EHR systems.
2. **Pillar 2: Distributed State Mesh (NATS JetStream + SQLite WAL):** Minimal friction adoption with zero database server setup; horizontally scales pub/sub across multi-nurse workstations with sub-millisecond synchronization.
3. **Pillar 3: Local Med-Aligned SLM Core (`LLMTriageEngine`):** Sub-3B parameter open-weights model (e.g. Gemma-2-2B / Qwen2.5-1.5B) fine-tunable on local hospital triage records via QLoRA for free-text paramedic run-sheet entity extraction without cloud leaks.
4. **Pillar 4: Facility Configuration Profiler:** Declarative YAML hospital profile schema adapting safe wait times and specialty triage paths between Rural Critical Access clinics and Level-1 Trauma centers.

### 10.2 Web & Cloud Deployment Guide (DEC-009)
1. **Live Public Web Hosting (Streamlit Community Cloud):**
   - Connect GitHub repo `starkaritra/patient-triage` at `https://share.streamlit.io`.
   - Branch: `v1` or `v2`. Main file path: `app.py`.
   - Generates a permanent public link (`https://patient-triage.streamlit.app`) with automatic redeployment on git push.
2. **Secondary Web Mirror (Hugging Face Spaces):**
   - Create Space with Streamlit SDK and sync repo.
3. **Hospital Pilot Edge Node:**
   - Single-node Docker deployment on hospital LAN (zero cloud leaks, HIPAA compliant).

---

### 11. Implementation Checklist (v1 Completed & v2 Roadmap)

### Completed on Branch `v1`:
- [x] **Data Contracts & High-Risk Meds (DEC-004):** Extended `triage/models.py` with `medications`, `allergies`, `vitals_history`, and `pseudo_id`.
- [x] **High-Risk Medication Danger Red-Lines:** Added Anticoagulant/DOAC head-trauma and immunocompromised fever alerts to `triage/rules.py`.
- [x] **Expanded 10-Rule Multi-System VOI Bank (DEC-005):** Expanded `triage/voi.py` covering ACS, Stroke, DVT/PE, Sepsis, Dehydration, Acute Abdomen, and Anaphylaxis.
- [x] **HIPAA Safe Harbor Audit De-Identification (DEC-006):** Implemented deterministic SHA-256 tokenization (`PT-HASH8`) in `triage/audit.py`.
- [x] **Vital Sign Velocity Tracking (DEC-007):** Added ΔVitals velocity scoring (ΔSBP, ΔHR, ΔSpO<sub>2</sub>) in `triage/queue.py`.
- [x] **Visual-First Clinical HUD:** Clean, responsive, zero-emoji dashboard with symmetric KPI header cards and collapsible drawers.

### Active Milestones for Branch `v2`:
- [ ] **Milestone 1: Declarative Facility Profiles (DEC-013):** Implement `config/facilities/` YAML schema loader (`level1_trauma.yaml`, `rural_critical_access.yaml`) and connect to `RuleRegistry` and `PatientQueue`.
- [ ] **Milestone 2: Concurrent Multi-Workstation Queue (DEC-011):** Implement `SqliteQueueRepository` with SQLite WAL mode and atomic transaction locking in `triage/queue.py`.
- [ ] **Milestone 3: HL7 FHIR v4 Ingestion Gateway (DEC-010):** Implement FastAPI router (`triage/api/fhir.py`) with `/Observation`, `/Patient`, and `/RiskAssessment` endpoints.
- [ ] **Milestone 4: Neurosymbolic Clinical SLM Core (DEC-012):** Implement `LLMTriageEngine` with free-text note parsing, local Ollama/fallback provider, and deterministic safety veto stops.
- [ ] **Milestone 5: Multi-Facility & Paramedic HUD Workstations:** Add live facility switching and paramedic free-text intake to the Streamlit Clinical HUD.

---

## 12. Verification & Acceptance Criteria (v2)

1. **Deterministic Safety Veto Invariant:** Physiological red-lines and high-risk medication stops ALWAYS override and veto any SLM candidate tier.
2. **FHIR Interoperability Compliance:** Ingests standard HL7 FHIR v4 JSON Observation/Patient bundles and exports compliant `RiskAssessment` resources.
3. **Multi-Workstation Concurrency:** Multiple browser tabs/tablets concurrently updating queue state without lockups or state loss (backed by SQLite WAL).
4. **Sub-second Execution:** Latency strictly < 50 ms for deterministic core and < 100 ms for local SLM entity extraction.
5. **HIPAA Safe Harbor Compliance:** Zero plaintext patient full names persisted in audit ledgers at rest.