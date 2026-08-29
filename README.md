# PatientTriage.ai

> **Explainable, Safety-Biased Clinical Decision-Support Triage System (v2)**  
> Features dynamic deterioration tracking, active Value-of-Information (VOI) questioning, HL7 FHIR v4 ingestion, neurosymbolic Clinical SLM narrative parsing, and a HIPAA Safe Harbor regulatory audit trail.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://patient-triage-as.streamlit.app/)

### 🌐 Live Public Demonstration: [https://patient-triage-as.streamlit.app/](https://patient-triage-as.streamlit.app/)

---

## 1. Quickstart & Local Execution

It is strongly recommended to run this project inside an isolated Python virtual environment (`.venv`).

### Step 1: Create & Activate the Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
*(If script execution is restricted in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, or use CMD: `.venv\Scripts\activate.bat`)*

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 3: Run Automated Verification Tests

Verify all 5 architectural milestones (Facility Profiles, SQLite WAL Concurrency, FHIR Ingestion, Neurosymbolic SLM, 20-Patient Cohort):

```bash
python tests/test_v2_milestones.py
```

---

### Step 4: Launch the Clinical Decision Support HUD

```bash
streamlit run app.py
```

The clinical dashboard will open in your browser at `http://localhost:8501`.

---

## 2. Key Clinical & Architectural Capabilities (v2)

* **Age-Stratified Physiological Red-Lines:** Deterministic safety stops calibrated against PEWS (Pediatric), NEWS2 (Adult), and qSOFA (Geriatric) with sub-millisecond evaluation (<1ms SLA).
* **Asymmetric Clinical Safety Bias:** Missing an emergent patient (*under-triage*) is weighted 10x worse than over-triage; epistemic uncertainty (<70% confidence) automatically escalates acuity by +1 tier.
* **Expanded 10-Rule Active VOI Engine:** Targeted clinical follow-up prompts across Cardiovascular, Neurological, Pediatric, Surgical Abdomen, Immunologic, and Infectious syndromes with 1-click nurse action pills.
* **Vital Sign Velocity Radar ($\Delta\text{Vitals}$):** Multi-parametric deterioration scoring ($\Delta\text{SBP}$, $\Delta\text{HR}$, $\Delta\text{SpO}_2$) detects rapid decompensation before clinical time breaches.
* **Declarative Facility Profiles (Pillar 4):** YAML-driven configuration adapting safe-wait windows, imaging capabilities (CT/MRI/Cath-lab), and transfer protocols between **Level-1 Trauma Centers**, **Community Hospitals**, and **Rural Critical Access Clinics**.
* **Concurrent SQLite WAL Queue (Pillar 2):** Persistent, multi-workstation state synchronization with zero external database setup.
* **HL7 FHIR v4 Interoperability (Pillar 1):** Ingests standard FHIR `Observation` bundles (LOINC codes) and exports compliant FHIR `RiskAssessment` resources.
* **Neurosymbolic Clinical SLM Core (Pillar 3):** Local Small Language Model narrative entity extractor parsing free-text paramedic run-sheets with **strict deterministic physiological red-line veto stops**.
* **HIPAA Safe Harbor Audit Ledger:** Append-only regulatory log with deterministic SHA-256 pseudonymization (`PT-HASH8`) at rest.

---

## 3. Project Memory & Embedded Knowledge Graph

This project uses an embedded project-local knowledge graph (`.kgraph`) to persist component topology, clinical invariants, and architectural decisions.

```bash
# Recall full knowledge graph topology & provenance facts
python .kgraph/kgraph.py recall

# View layered architecture & clinical data flow
python .kgraph/kgraph.py arch

# Verify integrity of file paths and node references
python .kgraph/kgraph.py verify
```

---

## 4. Repository & Architecture Documentation

- [**architecture.md**](architecture.md) — End-to-end system topology, latency SLAs, mathematical formulas, FHIR schemas, and upgrade/swap matrices.
- [**decisions.md**](decisions.md) — Architectural Decision Records (ADRs: DEC-001 through DEC-013).
- [**handoff.md**](handoff.md) — Master clinical blueprint, problem statement, 20-patient benchmark cohort, and milestone verification log.
- [**config/facilities/**](config/facilities/) — Declarative YAML hospital profile definitions (`community_hospital.yaml`, `level1_trauma.yaml`, `rural_critical_access.yaml`).

---

## 5. Branch Structure

- **`mvp`**: Frozen Round 2 prototype baseline (deterministic algorithmic core, basic VOI, initial queue radar).
- **`v1`**: Hardened v1 release (graded history/medication profiler, 10-rule VOI bank, HIPAA Safe Harbor pseudonymization, vital velocity tracking, responsive UI).
- **`v2`** *(Active)*: Multi-pillar distributed architecture, FHIR v4 gateway, SQLite WAL concurrency, neurosymbolic SLM narrative parser, and multi-facility profiles.