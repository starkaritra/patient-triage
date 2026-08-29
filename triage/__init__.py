"""PatientTriage.ai Core Engine Package."""

from triage.models import AgeCategory, PatientRecord, TriageResult, Vitals
from triage.rules import AgeVitalThresholds, RuleRegistry, evaluate_red_lines
from triage.engine import BaseTriageEngine, AlgorithmicTriageEngine
from triage.voi import VOIEngine
from triage.queue import PatientQueue, QueueRepository, InMemoryQueueRepository
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
    "PatientQueue",
    "QueueRepository",
    "InMemoryQueueRepository",
    "AuditLogger",
    "AuditRepository",
    "FileAuditRepository",
    "BENCHMARK_COHORT",
    "BENCHMARK_COHORT_20",
    "load_benchmark_cohort",
]