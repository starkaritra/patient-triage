# PatientTriage.ai — System Architecture & Distributed Blueprint

## 1. System Topology
            +----------------------------------------------+
              |           Clinical Client Fleet              |
              |  (Nurse Workstations, Tablets, Intake HUD)   |
              +----------------------------------------------+
                                     │
                                     ▼ (REST / WebSocket)
+─────────────────────────────────────────────────────────────────────────────+ | Application / Service Layer | | | | +-----------------------+ +-------------------+ +-------------+ | | | BaseTriageEngine | | VOI Engine | | Deterioration| | | | (Algorithmic / ML) | | (Active Q&A) | | Radar | | | +-----------┬-----------+ +---------┬---------+ +------┬------+ | | │ │ │ | +───────────────┼───────────────────────────┼──────────────────────┼──────────+ ▼ ▼ ▼ +─────────────────────────────────────────────────────────────────────────────+ | Repository Abstraction | | | | +───────────────────────────+ +────────────────────────────+ | | | QueueRepository | | AuditRepository | | | +─────────────┬─────────────+ +──────────────┬─────────────+ | +─────────────────────┼──────────────────────────────────┼────────────────────+ │ │ ┌────────────┴────────────┐ ┌────────────┴────────────┐ ▼ ▼ ▼ ▼ [In-Memory Store] [Redis Cache] [Local JSON/WAL] [PostgreSQL DB] (Local Dev / <1µs) (Prod Queue) (Local Dev) (Audit Ledger)


## 2. Latency Budget & Asymmetric Safety
- **Total Intake-to-Score SLA:** $<50\text{ms}$ (Current deterministic core: $\approx 0.8\text{ms}$).
- **Queue Priority Invariant:** $\text{Priority} = (6 - \text{ESI}) \times 100 + \left(\frac{\text{Wait}}{\text{SafeThreshold}}\right) \times 50 + \Delta \text{Vitals Penalty}$.
- **Safety Bias:** Low confidence ($<70\%$) on ambiguous or high-risk presentations automatically escalates acuity tier by $+1$.