# Architectural Decision Records (ADRs) — PatientTriage.ai

## [DEC-001] Pydantic v2 Data Modeling & Contract Enforcement
- Date: 2026-08-29
- Status: accepted
- Context: Clinical data ingestion requires strict boundary validation, type safety, and zero-overhead JSON serialization for FHIR integration and audit trails.
- Options considered:
  - Option A: Standard `@dataclass` — Minimal overhead, but lacks runtime boundary validation.
  - Option B: `pydantic.BaseModel` (v2) — Strict schema validation, automatic JSON export, zero-copy parsing.
- Decision: Adopt Pydantic v2 models for `Vitals`, `PatientRecord`, and `TriageResult`.
- Rationale: Prevents silent data corruption in clinical vitals and standardizes serialization for distributed queue and audit persistence.
- Consequences: Requires `pydantic>=2.0` in `requirements.txt`.

---

## [DEC-002] Declarative Rule Registry for Physiological Red-Lines
- Date: 2026-08-29
- Status: accepted
- Context: Age-stratified thresholds (PEWS, NEWS2, qSOFA) and red-line clinical alerts must be auditable and isolated from execution mechanics.
- Options considered:
  - Option A: Procedural nested if-else trees — High cyclomatic complexity and difficult to inspect.
  - Option B: Declarative rule registry with typed evaluators — Clean separation of clinical logic from engine orchestration.
- Decision: Implement a declarative `RuleRegistry` holding structured physiological rules.
- Rationale: Guarantees deterministic $<1\text{ms}$ evaluation while enabling transparent explanation extraction for UI audit views.
- Consequences: Decouples clinical logic from `BaseTriageEngine` implementations.

---

## [DEC-003] Pluggable Repository Pattern for Distributed Queue & Audit Store
- Date: 2026-08-29
- Status: accepted
- Context: The prototype requires zero-friction local execution ($<50\text{ms}$ latency budget), while production mandates a distributed multi-nurse system backed by Redis caching and SQL durability.
- Options considered:
  - Option A: In-Memory `st.session_state` only — Zero setup, but fails multi-clinician concurrency.
  - Option B: Hardcoded Redis + PostgreSQL requirement — Production-grade, but introduces local setup friction.
  - Option C: Abstract `QueueRepository` and `AuditRepository` interfaces with In-Memory default and Redis/SQL pluggable adapters.
- Decision: Adopt Option C (Repository Pattern).
- Rationale: Provides sub-millisecond local execution out of the box while making production transition frictionless via configuration switches (`QUEUE_BACKEND=redis_sql`).
- Consequences: Core domain logic interacts purely with repository interfaces.

---

## [DEC-004] Graded History Completeness & High-Risk Medication Profiling (v1)
- Date: 2026-08-30
- Status: accepted
- Context: Binary check of patient history (`len(history) == 0`) misses partial record risks (e.g. patients on Warfarin/DOACs or immunosuppressive therapy presenting with minor trauma or low-grade fevers).
- Options considered:
  - Option A: Binary presence check only — Simple, but treats a patient with only an allergy listed the same as a complete EHR dossier.
  - Option B: Graded history scoring with structured medication/allergy extraction — Scores history completeness into a continuous penalty $P_{\text{data}}$ ($0.00$ to $0.15$) and flags high-risk medication categories (anticoagulants, antiplatelets, insulin, immunosuppressants).
- Decision: Adopt Option B.
- Rationale: Protects occult bleeders (e.g. elderly falls on Warfarin) and septic immunocompromised patients from under-triage while refining epistemic confidence scoring.
- Consequences: Extends `PatientRecord` schema with `medications` and `allergies` fields.

---

## [DEC-005] Expanded Multi-System Clinical VOI Question Bank (v1)
- Date: 2026-08-30
- Status: accepted
- Context: Initial prototype contained 5 VOI rules, leaving gaps in common acute presentations like pediatric dehydration, surgical peritonitis, sepsis hypoperfusion, and evolving anaphylaxis.
- Options considered:
  - Option A: Retain 5 baseline rules — Lightweight, but limited diagnostic coverage.
  - Option B: Comprehensive 10-rule emergency differential bank covering Cardiovascular, Neurological, Pediatric, Surgical Abdomen, Immunologic, and Infectious disease syndromes.
- Decision: Adopt Option B.
- Rationale: Collapses entropy across all major ESI-2 trigger categories without introducing LLM non-determinism.
- Consequences: Expands `VOIEngine` rule registry with deterministic clinical condition triggers and score modifiers.

---

## [DEC-006] HIPAA Safe Harbor Deterministic Pseudonymization at Rest (v1)
- Date: 2026-08-30
- Status: accepted
- Context: Writing raw patient names to `audit_log.json` violates HIPAA Safe Harbor (45 CFR § 164.514) and EU MDR confidentiality requirements if logs are exported or analyzed.
- Options considered:
  - Option A: Plaintext logging — Zero implementation effort, but fails health data privacy standards.
  - Option B: Full database encryption only — Protects storage, but log exports still contain plaintext names.
  - Option C: Deterministic SHA-256 pseudonymization with salted tokenization (`PT-HASH8`) and separated demographic metadata in audit persistence.
- Decision: Adopt Option C.
- Rationale: Guarantees de-identification at rest in `audit_log.json` while maintaining referential integrity across audit events.
- Consequences: `AuditLogger` automatically generates a deterministic pseudonym `pseudo_id` and redacts patient full names in persisted JSON records.

---

## [DEC-007] Multi-Parametric Vital Sign Velocity (ΔVitals) & Deterioration Tracking (v1)
- Date: 2026-08-30
- Status: accepted
- Context: Static wait-time degradation does not capture rapid decompensation velocity (e.g. dropping SBP by 20mmHg or climbing HR by 25bpm over 15 minutes in the waiting room).
- Options considered:
  - Option A: Time-only wait penalty — Simple, but blind to physiological deterioration trends.
  - Option B: Serial vital history with parametric velocity penalty $\Delta\text{Vitals} = f(\Delta\text{SBP}, \Delta\text{HR}, \Delta\text{SpO}_2, \Delta\text{GCS})$.
- Decision: Adopt Option B.
- Rationale: Elevates rapidly deteriorating patients to top of the queue before full clinical breach occurs.
- Consequences: Adds `vitals_history: List[Vitals]` to `PatientRecord` and refines `calculate_priority_score()` in `triage/queue.py`.

---

## [DEC-008] Future Horizon (v2) Distributed Systems & Clinical SLM Architecture
- Date: 2026-08-30
- Status: proposed (target: v2)
- Context: Planning the production evolution across interoperability, distributed multi-nurse concurrency, local clinical intelligence, and multi-hospital customization.
- Decisions & Chosen Options:
  1. **Pillar 1 (Interoperability):** Embedded FastAPI FHIR v4 Listener (`/Observation`, `/Patient`) for real-time bedside monitor streaming.
  2. **Pillar 2 (Distributed Mesh):** NATS JetStream mesh with SQLite/WAL fallback for zero-ops local execution scaling to horizontal multi-nurse clusters with sub-millisecond pub/sub.
  3. **Pillar 3 (Clinical SLM):** Medically aligned Small Language Model (<3B parameters, e.g. Gemma-2-2B-IT or Qwen2.5-1.5B) fine-tunable locally via QLoRA on local hospital records for unstructured triage note entity extraction.
  4. **Pillar 4 (Facility Profiler):** Declarative YAML facility configuration schema (`config/facilities/*.yaml`) adapting triage rules between Rural Critical Access clinics and Level-1 Trauma centers.