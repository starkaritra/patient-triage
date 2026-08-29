"""
Data models and schemas for PatientTriage.ai.
Enforces validation and type safety using Pydantic v2.
"""

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
    """Physiological measurements at triage intake."""
    age: float = Field(..., ge=0.0, le=125.0, description="Age in years (decimal for infants, e.g. 0.33 for 4mo)")
    heart_rate: int = Field(..., ge=20, le=300, description="Beats per minute")
    systolic_bp: int = Field(..., ge=30, le=300, description="Systolic blood pressure in mmHg")
    diastolic_bp: int = Field(..., ge=20, le=200, description="Diastolic blood pressure in mmHg")
    resp_rate: int = Field(..., ge=4, le=100, description="Breaths per minute")
    spo2: float = Field(..., ge=50.0, le=100.0, description="Oxygen saturation percentage")
    temp_celsius: float = Field(..., ge=25.0, le=45.0, description="Core temperature in Celsius")
    pain_scale: int = Field(0, ge=0, le=10, description="Self-reported or assessed pain scale (0-10)")

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


class PatientRecord(BaseModel):
    """Comprehensive patient state container."""
    id: str = Field(..., description="Unique patient identifier, e.g. P-001")
    name: str = Field(..., description="Full patient name")
    vitals: Vitals
    chief_complaint: str = Field(..., min_length=2, description="Primary presenting complaint")
    history: List[str] = Field(default_factory=list, description="Past medical history, meds, allergies")
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
        return len(self.history) == 0


class TriageResult(BaseModel):
    """Standardized decision payload from any BaseTriageEngine implementation."""
    esi_level: int = Field(..., ge=1, le=5, description="Assigned ESI tier (1 to 5)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence metric (0.0 to 1.0)")
    primary_risk_factors: List[str] = Field(default_factory=list, description="Identified risk factors")
    is_ambiguous: bool = Field(False, description="True if diagnostic entropy triggers active questioning")
    recommended_followups: List[str] = Field(default_factory=list, description="Targeted VOI questions")
    deterministic_rule_hit: bool = Field(False, description="True if caught by hard safety stop")
    explanation: List[str] = Field(default_factory=list, description="Clinical bullet points explaining decision")