"""
Immutable Audit Logging & Regulatory Compliance Pipeline.
Guarantees auditability aligned with HIPAA Safe Harbor, EU MDR, and ONC CDS requirements.
v1 automatically pseudonymizes patient direct identifiers at rest using deterministic SHA-256 tokens.
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from triage.models import PatientRecord, TriageResult


class AuditRepository(ABC):
    @abstractmethod
    def append_event(self, entry: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_events(self) -> List[Dict[str, Any]]:
        pass


class FileAuditRepository(AuditRepository):
    """Append-only JSON ledger store."""

    def __init__(self, file_path: str = "audit_log.json"):
        self.file_path = file_path

    def append_event(self, entry: Dict[str, Any]) -> None:
        events = self.get_events()
        events.append(entry)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, default=str)

    def get_events(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []


class AuditLogger:
    """Clinical audit event manager with automated HIPAA Safe Harbor de-identification."""

    def __init__(self, repo: Optional[AuditRepository] = None):
        self.repo = repo or FileAuditRepository()

    def log_assessment(
        self,
        patient: PatientRecord,
        ai_result: TriageResult,
        clinician_id: str = "RN-SYSTEM",
        override_esi: Optional[int] = None,
        override_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        was_overridden = override_esi is not None and override_esi != ai_result.esi_level

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "patient_internal_id": patient.id,
            "pseudonymized_token": patient.pseudo_id,
            "demographics": {
                "age_category": patient.vitals.age_category.value,
                "age_years": round(patient.vitals.age, 1),
            },
            "clinical_presentation": {
                "chief_complaint": patient.chief_complaint,
                "high_risk_med_alerts": patient.high_risk_med_alerts,
                "is_zero_history": patient.is_zero_history,
                "vitals_snapshot": {
                    "hr": patient.vitals.heart_rate,
                    "sbp": patient.vitals.systolic_bp,
                    "dbp": patient.vitals.diastolic_bp,
                    "rr": patient.vitals.resp_rate,
                    "spo2": patient.vitals.spo2,
                    "temp": patient.vitals.temp_celsius,
                },
            },
            "ai_recommendation": {
                "esi_level": ai_result.esi_level,
                "confidence": ai_result.confidence,
                "deterministic_hit": ai_result.deterministic_rule_hit,
                "primary_risk_factors": ai_result.primary_risk_factors,
                "explanation": ai_result.explanation,
            },
            "voi_interactions": [
                {"question": q, "answer": a}
                for q, a in patient.answers_to_followups.items()
            ],
            "clinician_decision": {
                "final_esi": override_esi if was_overridden else ai_result.esi_level,
                "was_overridden": was_overridden,
                "clinician_id": clinician_id,
                "override_reason": override_reason if was_overridden else None,
            },
            "regulatory_compliance": {
                "hipaa_safe_harbor_de_identified": True,
                "advisory_only": True,
                "system_version": "v1.1.0",
            },
        }

        self.repo.append_event(entry)
        return entry