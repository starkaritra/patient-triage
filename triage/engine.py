"""
Triage Decision Core.
Implements the abstract BaseTriageEngine contract and AlgorithmicTriageEngine.
"""

import time
from abc import ABC, abstractmethod
from typing import List, Tuple
from triage.models import AgeCategory, PatientRecord, TriageResult
from triage.rules import evaluate_red_lines
from triage.voi import VOIEngine


class BaseTriageEngine(ABC):
    """Abstract contract for swappable decision cores (algorithmic, heuristic, ML, LLM)."""

    @abstractmethod
    def evaluate(self, patient: PatientRecord) -> TriageResult:
        """Evaluates patient and returns standardized TriageResult."""
        pass


class AlgorithmicTriageEngine(BaseTriageEngine):
    """
    Deterministic safety-gate + rule-weighted clinical risk baseline.
    Zero external dependencies, sub-millisecond execution.
    """

    def evaluate(self, patient: PatientRecord) -> TriageResult:
        start_time = time.perf_counter()
        reasons: List[str] = []

        # Step 1: Physiological & Syndrome Red-Line Safety Check
        rule_hit, rule_risks, base_esi = evaluate_red_lines(patient)
        reasons.extend(rule_risks)

        # Step 2: Compute Epistemic Confidence Penalties
        confidence, ambiguity_flags = self._calculate_confidence(patient, rule_hit)
        is_ambiguous = confidence < 0.70

        # Step 3: Check Resource Requirements for Stable Cases
        if not rule_hit and base_esi >= 3:
            assigned_esi, resource_reasons = self._evaluate_resources(patient)
            base_esi = assigned_esi
            reasons.extend(resource_reasons)

        # Step 4: Active VOI Follow-Up Evaluation
        followup_questions = []
        if is_ambiguous:
            followup_questions = VOIEngine.get_candidate_questions(patient)
            reasons.append(f"Epistemic confidence low ({int(confidence*100)}%). Active VOI query required.")

        # Step 5: Incorporate Clinician Answers to VOI Follow-Ups
        if patient.answers_to_followups:
            voi_esi, conf_boost, voi_insights = VOIEngine.evaluate_response(patient)
            reasons.extend(voi_insights)
            if voi_esi is not None:
                base_esi = min(base_esi, voi_esi)
            confidence = min(1.0, confidence + conf_boost)
            is_ambiguous = confidence < 0.70

        # Step 6: Asymmetric Safety Escalation on Residual Uncertainty
        if is_ambiguous and base_esi > 2:
            base_esi -= 1
            reasons.append("Asymmetric Safety Gating: Urgency escalated by +1 tier due to uncollapsed ambiguity.")

        return TriageResult(
            esi_level=base_esi,
            confidence=round(confidence, 2),
            primary_risk_factors=rule_risks,
            is_ambiguous=is_ambiguous,
            recommended_followups=followup_questions,
            deterministic_rule_hit=rule_hit,
            explanation=reasons,
        )

    def _calculate_confidence(self, patient: PatientRecord, rule_hit: bool) -> Tuple[float, List[str]]:
        """Formula: Confidence = 1.0 - P_data - P_vitals - P_ambiguity - P_age_risk"""
        flags: List[str] = []
        penalty = 0.0

        # 1. Missing history penalty (P_data = 0.15)
        if patient.is_zero_history:
            penalty += 0.15
            flags.append("Zero medical history recorded (-15%)")

        # 2. Vital variance / borderline penalty (P_vitals = 0.10)
        v = patient.vitals
        if v.age_category == AgeCategory.ADULT and (95 <= v.heart_rate <= 108 or 138 <= v.systolic_bp <= 145):
            penalty += 0.10
            flags.append("Borderline gray-zone vital signs (-10%)")

        # 3. Symptom ambiguity penalty (P_ambiguity = 0.20)
        ambiguous_keywords = ["dizziness", "fatigue", "epigastric", "indigestion", "weakness", "debility", "palpitation"]
        if any(k in patient.chief_complaint.lower() for k in ambiguous_keywords):
            penalty += 0.20
            flags.append("High-entropy non-specific presentation (-20%)")

        # 4. Age risk penalty (P_age_risk = 0.10)
        if patient.vitals.age_category in (AgeCategory.INFANT, AgeCategory.GERIATRIC):
            if any(k in patient.chief_complaint.lower() for k in ["debility", "low intake", "fever", "fatigue", "shivering"]):
                penalty += 0.10
                flags.append("High-risk vulnerable age group with systemic complaint (-10%)")

        confidence = max(0.40, 1.0 - penalty)
        if rule_hit and confidence < 0.85:
            confidence = max(confidence, 0.88)  # High physiological red-line restores certainty

        return confidence, flags

    def _evaluate_resources(self, patient: PatientRecord) -> Tuple[int, List[str]]:
        """Estimates ESI 3 vs 4 vs 5 based on projected resource utilization."""
        complaint = patient.chief_complaint.lower()

        # ESI 5: Zero resource cases (suture removal, rx refill, minor superficial scrape)
        if any(w in complaint for w in ["suture removal", "prescription", "refill", "superficial", "scrape", "minor abrasion"]):
            return 5, ["Expected ED Resources: 0 (Fast-Track non-urgent)"]

        # ESI 4: 1 resource cases (simple sprain/x-ray, hives/oral antihistamine, simple suture)
        if any(w in complaint for w in ["ankle", "sprain", "twisted", "hives", "rash", "isolated laceration", "amoxicillin"]):
            return 4, ["Expected ED Resources: 1 (Plain X-ray, minor suture, or oral meds)"]

        # ESI 3: Multiple resources (Labs + IV + Imaging, e.g. acute RLQ pain, severe colic, chest workup)
        return 3, ["Expected ED Resources: 2+ (IV access, blood labs, and diagnostic imaging)"]