
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
- **Round 2 Baseline:** Fully deterministic physiological red-lines + statistical/heuristic scoring model + rule-indexed VOI question bank (runs locally, zero API dependency, $<50\text{ms}$ latency).
- **Future Extension:** Pluggable Fine-Tuned LLM or RAG differential agent by implementing a single adapter class without touching the UI, queue, or audit layers.

---

## 2. Clinical Framework & Safety Design

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

### 2.1 Age-Stratified Vital Thresholds (PEWS & NEWS2 Calibrated)
Thresholds are dynamically selected based on `age_category`:

| Vital Parameter | Infant (<1 yr) | Child (1–12 yrs) | Adult (13–64 yrs) | Geriatric (65+ yrs) |
| :--- | :--- | :--- | :--- | :--- |
| **Heart Rate (HR)** | Normal: 100–160<br>Critical: >180 / <80 | Normal: 70–120<br>Critical: >140 / <60 | Normal: 60–100<br>Critical: >120 / <50 | Normal: 60–90<br>Critical: >105 / <50 |
| **Respiratory (RR)** | Normal: 30–50<br>Critical: >60 / <20 | Normal: 18–30<br>Critical: >40 / <14 | Normal: 12–20<br>Critical: >28 / <10 | Normal: 12–20<br>Critical: >26 / <10 |
| **Systolic BP (SBP)**| Normal: 70–100<br>Critical: <70 | Normal: 85–115<br>Critical: <80 | Normal: 100–140<br>Critical: <90 / >190 | Normal: 110–145<br>Critical: <95 / >190 |
| **Temperature** | Fever: >38.0°C<br>Critical: $\ge$38.5°C | Fever: >38.3°C<br>Critical: $\ge$39.0°C | Fever: >38.3°C<br>Critical: $\ge$39.5°C | Hypothermia: <35.5°C<br>Fever: >37.8°C |
| **$\text{SpO}_2$** | Critical: <94% | Critical: <93% | Critical: <92% | Critical: <91% |

### 2.2 Asymmetric Clinical Loss Function
Missing a critical case (**under-triage**) is $10\times$ worse than over-prioritizing a stable patient (**over-triage**):
$$\text{Loss}(\text{True ESI } 1/2 \to \text{Assigned ESI } 3/4) \gg \text{Loss}(\text{True ESI } 4 \to \text{Assigned ESI } 3)$$
- **Rule:** If epistemic confidence is low ($<70\%$) on any high-risk symptom, the engine defaults to **escalating urgency by +1 tier** rather than defaulting to average acuity.

---

## 3. System Architecture & Module Contracts

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

### 3.1 Data Models (`triage/models.py`)

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

@dataclass
class Vitals:
    age: float
    heart_rate: int
    systolic_bp: int
    diastolic_bp: int
    resp_rate: int
    spo2: float
    temp_celsius: float
    pain_scale: int  # 0 to 10

@dataclass
class PatientRecord:
    id: str
    name: str
    age_category: str  # 'infant', 'child', 'adult', 'geriatric'
    vitals: Vitals
    chief_complaint: str
    history: List[str] = field(default_factory=list)  # Empty for zero-history patients
    arrival_time: datetime = field(default_factory=datetime.now)
    wait_time_minutes: int = 0
    assigned_esi: Optional[int] = None
    override_esi: Optional[int] = None
    override_reason: Optional[str] = None
    answers_to_followups: Dict[str, str] = field(default_factory=dict)

@dataclass
class TriageResult:
    esi_level: int                  # 1 (Resuscitation) to 5 (Non-urgent)
    confidence: float              # 0.0 to 1.0 (e.g. 0.85 = 85%)
    primary_risk_factors: List[str]
    is_ambiguous: bool
    recommended_followups: List[str]  # 1-2 targeted VOI questions
    deterministic_rule_hit: bool   # True if caught by hard safety stop
    explanation: str               # 2-3 bullet clinical reasoning
```

### 3.2 Swappable Engine Contract (`triage/engine.py`)

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
    Zero external dependencies, immediate execution.
    """
    def evaluate(self, patient: PatientRecord) -> TriageResult:
        # Step 1: Run deterministic physiological red-lines (PEWS/NEWS2)
        # Step 2: Calculate symptom risk weight & resource needs
        # Step 3: Compute confidence & ambiguity index
        # Step 4: Generate VOI questions if confidence < 0.70
        pass
```

---

## 4. Confidence Metric & Active VOI Question Engine

### 4.1 Confidence Score Formula
Confidence is derived from 4 penalized dimensions:
$$\text{Confidence} = 1.0 - P_{\text{data}} - P_{\text{vitals}} - P_{\text{ambiguity}} - P_{\text{age\_risk}}$$

1. **Missing History Penalty ($P_{\text{data}}$):** $0.15$ if `len(patient.history) == 0` (Zero-history patient).
2. **Vital Variance Penalty ($P_{\text{vitals}}$):** $0.10$ if vitals lie in borderline gray zones (e.g., HR 98–105 in adult).
3. **Symptom Ambiguity Penalty ($P_{\text{ambiguity}}$):** $0.20$ if complaint matches high-entropy differential sets (e.g., "Dizziness", "Fatigue", "Epigastric discomfort").
4. **Age Risk Penalty ($P_{\text{age\_risk}}$):** $0.10$ for infants ($<1\text{ yr}$) or geriatric patients ($>75\text{ yrs}$) presenting with non-specific systemic symptoms.

### 4.2 VOI (Value of Information) Question Mapping
When $\text{Confidence} < 0.70$, `triage/voi.py` triggers targeted clinical checks:

| Presenting Symptom / Category | Trigger Condition | High-Yield VOI Follow-Up Question | Impact on Re-assessment |
| :--- | :--- | :--- | :--- |
| **Epigastric Pain / Indigestion** | Adult/Geriatric, Diabetic or Female | *"Is there associated diaphoresis, nausea, or radiation to jaw/arm?"* | If Yes $\to$ Escalates to **ESI 2** (Atypical ACS). |
| **Vague Dizziness / Imbalance** | Geriatric or Hypertensive | *"Are there unilateral facial droop, arm drift, or speech changes (FAST)?"* | If Yes $\to$ Escalates to **ESI 2** (Stroke Alert). |
| **Calf Pain / Swelling** | Female on OCP or Recent Immobility | *"Is there unilateral leg swelling or shortness of breath on exertion?"* | If Yes $\to$ Escalates to **ESI 2** (DVT/PE risk). |
| **High Fever** | Infant (<1 yr) | *"Is the infant making wet diapers and making eye contact?"* | If No $\to$ Escalates to **ESI 2** (Decompensated sepsis). |
| **Palpitations & Paresthesia** | Young adult, SpO2 100% | *"Is there lightheadedness, chest pressure, or history of SVT?"* | If Yes $\to$ ESI 2/3 (ECG check); If No $\to$ ESI 4 (Panic check). |

---

## 5. Dynamic Queue Deterioration & 3× Surge Engine

### 5.1 Safe Wait Time Windows & Auto-Retriage Trigger
Each ESI tier has a strict maximum safe waiting threshold:
- **ESI 1:** $0\text{ min}$ (Immediate Bedding)
- **ESI 2:** $10\text{ min}$ max wait
- **ESI 3:** $30\text{ min}$ max wait
- **ESI 4:** $60\text{ min}$ max wait
- **ESI 5:** $120\text{ min}$ max wait

**Deterioration Score Formula:**
$$\text{Priority Score} = (6 - \text{ESI}) \times 100 + \left(\frac{\text{Wait Time}}{\text{Safe Threshold}}\right) \times 50 + \Delta \text{Vitals Penalty}$$
- If $\text{Wait Time} > \text{Safe Threshold}$, the UI highlights the patient in **flashing amber/red** with a `"RE-TRIAGE REQUIRED"` alert.
- If nurse inputs updated vitals showing decompensation (e.g., SBP drops from $115 \to 92$), the patient jumps to the top of the queue.

### 5.2 3× Surge Adaptation Mode
When the charge nurse toggles **Surge Mode**:
1. **Queue Re-balancing:** Patients are ranked by composite deterioration risk rather than arrival timestamp.
2. **Fast-Track Diversion:** Stable ESI 4 and ESI 5 patients are visually segregated into a separate "Fast-Track / Minor Injury Unit" queue to prevent ED bed blocking.
3. **Bottleneck Transparency:** Displays live telemetry: Beds Occupied, Waiting Room Count, Average Time-to-Doctor, and Re-Triage Alert Count.

---

## 6. Clinician Review & Immutable Audit Trail

### 6.1 Regulatory Compliance Guarantee (HIPAA / EU MDR / ONC CDS)
- AI recommendations are strictly advisory and never autonomously commit medical records.
- All assessments, nurse acceptances, and manual overrides are recorded in an append-only audit ledger (`audit_log.json`).

### 6.2 Audit Schema (`triage/audit.py`)
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

## 7. The 20-Patient Benchmark Cohort (`triage/cohort.py`)

| # | ID | Name & Age | Presentation & History | Vitals | Expected ESI & Conf | Test Objective |
|---|---|---|---|---|---|---|
| **1** | `P-001` | Baby Leo (4 mo) | High fever, lethargy, poor feeding. Zero history. | T: 38.9°C, HR: 188, RR: 54, SpO2: 96% | **ESI 2** (92% Conf) | Pediatric PEWS vital red-line. |
| **2** | `P-002` | Eleanor (78 yo F) | "Indigestion" and profound fatigue. Hx: Type 2 Diabetes. | T: 36.1°C, HR: 102, BP: 104/65, SpO2: 95% | **ESI 2** (65% $\to$ 85% post-VOI) | Geriatric atypical silent MI (ACS). |
| **3** | `P-003` | Marcus (34 yo M) | Severe mid-epigastric pain. Zero prior history. | T: 37.1°C, HR: 86, BP: 138/88, SpO2: 99% | **ESI 3** (55% Conf) | Zero-history baseline; triggers VOI. |
| **4** | `P-004` | David (67 yo M) | Sudden mild dizziness & left facial numbness. Hx: HTN. | T: 36.8°C, HR: 74, BP: 168/96, SpO2: 98% | **ESI 2** (60% Conf) | Ambiguous stroke mimic $\to$ VOI FAST. |
| **5** | `P-005` | Chloe (6 yo F) | Barking cough, inspiratory stridor at rest. Hx: Asthma. | T: 37.8°C, HR: 142, RR: 38, SpO2: 92% | **ESI 2** (90% Conf) | Pediatric airway compromise. |
| **6** | `P-006` | Frank (82 yo M) | Shivering, mild confusion. Hx: Dementia. | T: 35.2°C (Hypothermic), HR: 110, BP: 86/52 | **ESI 2** (95% Conf) | Occult geriatric sepsis (qSOFA red-line). |
| **7** | `P-007` | Jamal (28 yo M) | Sudden sharp chest pain after heavy deadlifting. | T: 36.6°C, HR: 88, BP: 122/78, SpO2: 99% | **ESI 3** (70% Conf) | Musculoskeletal vs Pleuritic check. |
| **8** | `P-008` | Maria (45 yo F) | Migrating RLQ abdominal pain, nausea. Hx: None. | T: 38.0°C, HR: 94, BP: 125/80, SpO2: 98% | **ESI 3** (80% Conf) | Acute appendicitis resource triage. |
| **9** | `P-009` | Sam (19 yo NB) | Inverted right ankle while running, bearing weight. | Vitals completely normal. Pain: 4/10. | **ESI 4** (95% Conf) | Fast-Track candidate under surge. |
| **10**| `P-010` | Arthur (72 yo M) | Ground-level mechanical fall, on Warfarin. Normal vitals. | T: 36.7°C, HR: 72, BP: 135/80, SpO2: 98% | **ESI 2** (85% Conf) | High-risk medication alert (Intracranial bleed). |
| **11**| `P-011` | Priya (29 yo F) | Rapid palpitations & tingling fingers. Zero history. | T: 36.7°C, HR: 138, BP: 132/84, SpO2: 100% | **ESI 3** (58% Conf) | SVT vs Panic attack $\to$ VOI ECG query. |
| **12**| `P-012` | Liam (8 yo M) | Superficial bicycle handlebar scrape. | Vitals normal. Pain: 2/10. | **ESI 5** (98% Conf) | Low-acuity non-urgent control. |
| **13**| `P-013` | Brenda (58 yo F) | Left calf aching & slight breathlessness. Recent flight. | T: 36.9°C, HR: 98, BP: 128/82, SpO2: 94% | **ESI 2** (62% Conf) | DVT / Pulmonary embolism risk. |
| **14**| `P-014` | Kenneth (61 yo M) | Sudden tearing back pain, syncope. Hx: HTN. | T: 36.2°C, HR: 114, BP: 84/48, SpO2: 94% | **ESI 1/2** (98% Conf) | Rupturing AAA / Hemorrhagic shock. |
| **15**| `P-015` | Zoe (22 yo F) | Severe sore throat, muffled voice, drooling. | T: 38.8°C, HR: 106, BP: 118/74, SpO2: 97% | **ESI 2** (90% Conf) | Airway threat (Peritonsillar abscess). |
| **16**| `P-016` | Robert (50 yo M) | Routine suture removal from laceration 10 days ago. | Vitals completely normal. | **ESI 5** (99% Conf) | Minimal resource utilization. |
| **17**| `P-017` | Evelyn (88 yo F) | General debility over 4 days, low intake. Zero records. | T: 36.0°C, HR: 60, BP: 108/68, SpO2: 95% | **ESI 3** (52% Conf) | Zero-history geriatric decline $\to$ VOI check. |
| **18**| `P-018` | Carlos (38 yo M) | Violent headache, photophobia, neck stiffness. | T: 39.4°C, HR: 118, BP: 130/85, SpO2: 97% | **ESI 2** (95% Conf) | Acute meningitis red flag. |
| **19**| `P-019` | Hannah (16 yo F) | Severe asthma flare, 2-word dyspnea. Hx: Asthma. | T: 37.0°C, HR: 126, RR: 32, SpO2: 90% | **ESI 2** (96% Conf) | Hypoxemic adolescent asthma exacerbation. |
| **20**| `P-020` | Tom (42 yo M) | Generalized hives after Amoxicillin, airway clear. | T: 36.8°C, HR: 82, BP: 124/80, SpO2: 99% | **ESI 4** (88% Conf) | Non-anaphylactic allergic reaction. |

---

## 8. Clinical Dashboard UI Specification (`app.py`)

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

## 9. Implementation Checklist for Coding Agents

### Step 1: Data Structures & Deterministic Rules
- [ ] Implement `triage/models.py` with standard dataclasses.
- [ ] Implement `triage/rules.py` with age-adjusted vital checks (PEWS, NEWS2, qSOFA).

### Step 2: Algorithmic Scorer & Active VOI
- [ ] Implement `triage/engine.py` with `BaseTriageEngine` and `AlgorithmicTriageEngine`.
- [ ] Implement `triage/voi.py` to trigger targeted questions on confidence $<70\%$.
- [ ] Integrate reciprocal confidence update when nurse answers VOI questions.

### Step 3: Dynamic Queue & Surge Simulator
- [ ] Implement `triage/queue.py` tracking wait times, safe thresholds, and priority re-ranking.
- [ ] Add deterioration trigger functions (`simulate_time_passage()`, `simulate_vital_drop()`).
- [ ] Implement Fast-Track queue splitting under 3× Surge Mode.

### Step 4: Audit Trail & Cohort Loader
- [ ] Implement `triage/audit.py` with file-backed JSON logging.
- [ ] Implement `triage/cohort.py` pre-loading all 20 benchmark records.

### Step 5: Interactive Streamlit Dashboard (`app.py`)
- [ ] Assemble the 3-tab UI.
- [ ] Add 1-click Preset Scenario buttons:
  - *Scenario A:* **"Pediatric Sepsis Gating"** (Baby Leo, `P-001`)
  - *Scenario B:* **"Ambiguous Geriatric ACS + VOI Interaction"** (Eleanor, `P-002`)
  - *Scenario C:* **"3× Surge Mode & Queue Deterioration Breach"** (Triggers queue re-ranking)
- [ ] Build Clinician Override modal with required justification capture.

---

## 10. Verification & Acceptance Criteria

1. **Zero Runtime Dependencies beyond Standard Stack:** Runs cleanly with `pip install streamlit pandas pydantic`.
2. **Sub-second Execution:** Every triage recommendation renders in $<50\text{ms}$.
3. **Cohort Coverage:** All 20 simulated patients evaluate correctly against their expected ESI band.
4. **Surge & Breach Visibility:** Toggling 3× Surge immediately elevates waiting breach cases to the top and routes ESI 4/5 cases to Fast-Track.
5. **Audit Integrity:** Every override writes a structured record to `audit_log.json` with timestamp, AI prediction, nurse override, and justification text.