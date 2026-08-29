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