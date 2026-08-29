"""PatientTriage.ai Core Engine Package (v2)."""

from triage.models import AgeCategory, PatientRecord, TriageResult, Vitals
from triage.rules import AgeVitalThresholds, RuleRegistry, evaluate_red_lines
from triage.engine import BaseTriageEngine, AlgorithmicTriageEngine
from triage.voi import VOIEngine
from triage.facility import FacilityProfile, load_facility_profile, list_available_facilities
from triage.queue import PatientQueue, QueueRepository, InMemoryQueueRepository, SqliteQueueRepository
from triage.audit import AuditLogger, AuditRepository, FileAuditRepository
from triage.cohort import BENCHMARK_COHORT, BENCHMARK_COHORT_20, load_benchmark_cohort

__all__ = [
    "AgeCategory",
    "Vitals",
    "PatientRecord",
    "TriageResult",
    "AgeVitalThresholds",
    "RuleRegistry",
    "evaluate_red_lines",
    "BaseTriageEngine",
    "AlgorithmicTriageEngine",
    "VOIEngine",
    "FacilityProfile",
    "load_facility_profile",
    "list_available_facilities",
    "PatientQueue",
    "QueueRepository",
    "InMemoryQueueRepository",
    "SqliteQueueRepository",
    "AuditLogger",
    "AuditRepository",
    "FileAuditRepository",
    "BENCHMARK_COHORT",
    "BENCHMARK_COHORT_20",
    "load_benchmark_cohort",
]