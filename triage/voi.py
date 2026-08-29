"""
Value-of-Information (VOI) Active Questioning Engine.
Triggers targeted follow-ups on high-entropy presentations to collapse diagnostic uncertainty.
"""

from typing import Dict, List, Optional, Tuple
from triage.models import AgeCategory, PatientRecord


class VOIEngine:
    """Active clinical query engine."""

    # VOI rule table mapped to presenting triggers (Section 4.2)
    VOI_RULES = [
        {
            "id": "VOI-ACS",
            "condition": lambda p: ("epigastric" in p.chief_complaint.lower() or "indigestion" in p.chief_complaint.lower() or "fatigue" in p.chief_complaint.lower())
            and (p.vitals.age_category in (AgeCategory.ADULT, AgeCategory.GERIATRIC) or any("diabetes" in h.lower() for h in p.history)),
            "question": "Is there associated diaphoresis, nausea, or radiation to jaw/arm?",
            "impact": "If YES, escalates to ESI 2 (Atypical ACS / Silent MI).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "jaw" in ans.lower() or "sweat" in ans.lower() or "cold" in ans.lower(), 2),
        },
        {
            "id": "VOI-STROKE",
            "condition": lambda p: ("dizziness" in p.chief_complaint.lower() or "imbalance" in p.chief_complaint.lower() or "facial" in p.chief_complaint.lower())
            and (p.vitals.age_category == AgeCategory.GERIATRIC or any("htn" in h.lower() or "hypertension" in h.lower() for h in p.history)),
            "question": "Are there unilateral facial droop, arm drift, or speech changes (FAST)?",
            "impact": "If YES, escalates to ESI 2 (Stroke Alert / CVA).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "droop" in ans.lower() or "drift" in ans.lower() or "slurred" in ans.lower(), 2),
        },
        {
            "id": "VOI-DVT-PE",
            "condition": lambda p: ("calf" in p.chief_complaint.lower() or "leg" in p.chief_complaint.lower() or "flight" in p.chief_complaint.lower() or "breathless" in p.chief_complaint.lower()),
            "question": "Is there unilateral leg swelling or shortness of breath on exertion?",
            "impact": "If YES, escalates to ESI 2 (DVT / Pulmonary Embolism risk).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "swelling" in ans.lower() or "short" in ans.lower(), 2),
        },
        {
            "id": "VOI-PED-SEPSIS",
            "condition": lambda p: p.vitals.age_category == AgeCategory.INFANT and ("fever" in p.chief_complaint.lower() or p.vitals.temp_celsius >= 38.0),
            "question": "Is the infant making wet diapers and maintaining eye contact?",
            "impact": "If NO, escalates to ESI 2 (Decompensated pediatric sepsis).",
            "eval_answer": lambda ans: ("no" in ans.lower() or "poor" in ans.lower() or "lethargic" in ans.lower(), 2),
        },
        {
            "id": "VOI-SVT-PANIC",
            "condition": lambda p: ("palpitation" in p.chief_complaint.lower() or "tingling" in p.chief_complaint.lower() or "racing" in p.chief_complaint.lower()),
            "question": "Is there lightheadedness, chest pressure, or a prior history of SVT?",
            "impact": "If YES -> ESI 2/3 (ECG check); If NO -> ESI 4 (Panic / Anxiety check).",
            "eval_answer": lambda ans: (True, 2 if ("yes" in ans.lower() or "pressure" in ans.lower() or "svt" in ans.lower()) else 4),
        },
    ]

    @classmethod
    def get_candidate_questions(cls, patient: PatientRecord) -> List[str]:
        questions = []
        for rule in cls.VOI_RULES:
            try:
                if rule["condition"](patient):
                    questions.append(rule["question"])
            except Exception:
                continue
        return questions[:2]

    @classmethod
    def evaluate_response(cls, patient: PatientRecord) -> Tuple[Optional[int], Optional[float], List[str]]:
        """Evaluates answered VOI queries to adjust ESI and recover epistemic confidence."""
        escalated_esi: Optional[int] = None
        confidence_boost = 0.0
        insights: List[str] = []

        for q, ans in patient.answers_to_followups.items():
            if not ans.strip():
                continue
            for rule in cls.VOI_RULES:
                if rule["question"] == q:
                    triggered, target_esi = rule["eval_answer"](ans)
                    if triggered:
                        escalated_esi = min(escalated_esi, target_esi) if escalated_esi else target_esi
                        insights.append(f"VOI Response positive for {rule['id']}: Urgency confirmed at ESI {target_esi}")
                        confidence_boost += 0.20
                    else:
                        insights.append(f"VOI Response negative for {rule['id']}: Down-escalated ambiguity.")
                        confidence_boost += 0.15

        return escalated_esi, min(confidence_boost, 0.30), insights