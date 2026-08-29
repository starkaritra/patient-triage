"""
Data models and schemas for PatientTriage.ai.
Enforces validation and type safety using Pydantic v2.
Includes v1 extensions for medications, allergies, serial vitals history, and HIPAA Safe Harbor pseudonymization.
"""

import hashlib
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AgeCategory(str, Enum):
    INFANT = "infant"          # < 1 yr
    CHILD = "child"            # 1–12 yrs
    ADULT = "adult"            # 13–64 yrs
    GERIATRIC = "geriatric"    # 65+ yrs


class Vitals(BaseModel):
    """Physiological measurements at triage intake or serial waiting room reassessment."""
    age: float = Field(..., ge=0.0, le=125.0, description="Age in years (decimal for infants, e.g. 0.33 for 4mo)")
    heart_rate: int = Field(..., ge=20, le=300, description="Beats per minute")
    systolic_bp: int = Field(..., ge=30, le=300, description="Systolic blood pressure in mmHg")
    diastolic_bp: int = Field(..., ge=20, le=200, description="Diastolic blood pressure in mmHg")
    resp_rate: int = Field(..., ge=4, le=100, description="Breaths per minute")
    spo2: float = Field(..., ge=50.0, le=100.0, description="Oxygen saturation percentage")
    temp_celsius: float = Field(..., ge=25.0, le=45.0, description="Core temperature in Celsius")
    pain_scale: int = Field(0, ge=0, le=10, description="Self-reported or assessed pain scale (0-10)")
    recorded_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of vital capture")

    @property
    def age_category(self) -> AgeCategory:
        """Dynamically computes clinical age category."""
        if self.age < 1.0:
            return AgeCategory.INFANT
        elif self.age <= 12.0:
            return AgeCategory.CHILD
        elif self.age <= 64.0:
            return AgeCategory.ADULT
        else:
            return AgeCategory.GERIATRIC


# Known high-risk medication categories (Anticoagulants, Antiplatelets, Immunosuppressants, Insulin)
HIGH_RISK_MED_KEYWORDS = {
    "anticoagulant": ["warfarin", "coumadin", "eliquis", "apixaban", "xarelto", "rivaroxaban", "pradaxa", "dabigatran", "heparin", "enoxaparin", "lovenox"],
    "antiplatelet": ["plavix", "clopidogrel", "brilinta", "ticagrelor", "aspirin"],
    "immunosuppressant": ["prednisone", "methotrexate", "tacrolimus", "cyclosporine", "humira", "chemotherapy", "rituximab", "mycophenolate"],
    "hypoglycemic": ["insulin", "glipizide", "glimepiride", "metformin"],
}


class PatientRecord(BaseModel):
    """Comprehensive patient state container (v1 hardened)."""
    id: str = Field(..., description="Unique patient identifier, e.g. P-001")
    name: str = Field(..., description="Full patient name")
    vitals: Vitals
    chief_complaint: str = Field(..., min_length=2, description="Primary presenting complaint")
    history: List[str] = Field(default_factory=list, description="Past medical diagnoses & surgical history")
    medications: List[str] = Field(default_factory=list, description="Current home/prescribed medications")
    allergies: List[str] = Field(default_factory=list, description="Documented drug and food allergies")
    vitals_history: List[Vitals] = Field(default_factory=list, description="Serial recorded vitals for velocity tracking")
    arrival_time: datetime = Field(default_factory=datetime.utcnow, description="Arrival timestamp")
    wait_time_minutes: int = Field(0, ge=0, description="Elapsed wait time in minutes")
    assigned_esi: Optional[int] = Field(None, ge=1, le=5, description="Active algorithmic ESI tier")
    override_esi: Optional[int] = Field(None, ge=1, le=5, description="Clinician overridden ESI tier")
    override_reason: Optional[str] = Field(None, description="Mandatory clinical justification for override")
    clinician_id: Optional[str] = Field(None, description="Identifier of triaging nurse/physician")
    answers_to_followups: Dict[str, str] = Field(default_factory=dict, description="Active VOI responses")

    @property
    def effective_esi(self) -> Optional[int]:
        return self.override_esi if self.override_esi is not None else self.assigned_esi

    @property
    def is_zero_history(self) -> bool:
        """Returns True if intake has zero prior records, medications, or allergies."""
        return len(self.history) == 0 and len(self.medications) == 0 and len(self.allergies) == 0

    @property
    def is_partial_history(self) -> bool:
        """Returns True if patient has some information but missing key medication/diagnosis detail."""
        if self.is_zero_history:
            return False
        return len(self.history) == 0 or len(self.medications) == 0

    @property
    def high_risk_med_alerts(self) -> List[str]:
        """Scans medications and history for critical clinical drug classes."""
        alerts = []
        combined_text = " ".join(self.medications + self.history).lower()
        for category, drugs in HIGH_RISK_MED_KEYWORDS.items():
            for drug in drugs:
                if drug in combined_text:
                    alerts.append(f"High-Risk {category.capitalize()}: {drug.capitalize()}")
                    break
        return alerts

    @property
    def pseudo_id(self) -> str:
        """Deterministic HIPAA Safe Harbor pseudonym (SHA-256 token)."""
        token = hashlib.sha256(f"{self.id}-{self.name}".encode("utf-8")).hexdigest()[:8].upper()
        return f"PT-{token}"


class TriageResult(BaseModel):
    """Standardized decision payload from any BaseTriageEngine implementation."""
    esi_level: int = Field(..., ge=1, le=5, description="Assigned ESI tier (1 to 5)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence metric (0.0 to 1.0)")
    primary_risk_factors: List[str] = Field(default_factory=list, description="Identified risk factors")
    is_ambiguous: bool = Field(False, description="True if diagnostic entropy triggers active questioning")
    recommended_followups: List[str] = Field(default_factory=list, description="Targeted VOI questions")
    deterministic_rule_hit: bool = Field(False, description="True if caught by hard safety stop")
    explanation: List[str] = Field(default_factory=list, description="Clinical bullet points explaining decision")