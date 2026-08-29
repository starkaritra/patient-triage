# PatientTriage.ai

> **Explainable, Safety-Biased Clinical Decision-Support Triage System**  
> Features dynamic deterioration tracking, active value-of-information (VOI) questioning, and regulatory audit trail.

---

## 1. Quickstart (Virtual Environment)

It is strongly recommended to run this project inside an isolated Python virtual environment (`.venv`).

### Step 1: Create the Virtual Environment

**Windows (PowerShell / Command Prompt):**
```powershell
python -m venv .venv
```

**macOS / Linux:**
```bash
python3 -m venv .venv
```

---

### Step 2: Activate the Virtual Environment

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```
*(If script execution is restricted in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, or use CMD: `.venv\Scripts\activate.bat`)*

**macOS / Linux:**
```bash
source .venv/bin/activate
```

---

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 4: Launch the Streamlit Clinical HUD

```bash
streamlit run app.py
```

The clinical dashboard will open in your browser at `http://localhost:8501`.

---

## 2. Project Memory & Knowledge Graph

This project uses an embedded knowledge graph (`.kgraph`) to persist component topology, clinical invariants, and architectural decisions.

```bash
# Recall full knowledge map & provenance facts
python .kgraph/kgraph.py recall

# View layered architecture & clinical data flow
python .kgraph/kgraph.py arch

# Verify integrity of file paths and references
python .kgraph/kgraph.py verify
```

---

## 3. Project Documentation

- [architecture.md](architecture.md) — System topology, distributed blueprint, latency budget, and mathematical formulas.
- [decisions.md](decisions.md) — Architectural Decision Records (ADRs: DEC-001 through DEC-003).
- [handoff.md](handoff.md) — Master clinical blueprint, 20-patient benchmark cohort, and UI specifications.

---

## 4. Key Clinical Features

- **Age-Stratified Physiological Red-Lines:** Deterministic safety stops calibrated against PEWS (Pediatric), NEWS2 (Adult), and qSOFA (Geriatric).
- **Asymmetric Safety Loss Function:** Epistemic uncertainty (<70% confidence) automatically escalates acuity tier by +1 to prevent under-triage.
- **Active VOI Questioning:** Dynamically prompts targeted follow-up queries to collapse diagnostic ambiguity.
- **Dynamic Deterioration Radar:** Real-time priority degradation based on safe wait-time thresholds.
- **3× Surge Adaptation Mode:** Auto-rebalances queue and diverts low-acuity (ESI 4/5) patients to Fast-Track lanes.
- **Regulatory Audit Trail:** Append-only JSON ledger capturing AI recommendations and mandatory clinician override justifications.