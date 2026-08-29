"""
Value-of-Information (VOI) Active Questioning Engine (v1 Expanded).
Triggers targeted follow-ups on high-entropy presentations across 10 multi-system clinical domains
to collapse diagnostic uncertainty and resolve ambiguous ESI boundaries.
"""

from typing import Dict, List, Optional, Tuple
from triage.models import AgeCategory, PatientRecord


class VOIEngine:
    """Active clinical query engine with expanded 10-rule emergency differential bank."""

    VOI_RULES = [
        # 1. Atypical ACS / Silent MI
        {
            "id": "VOI-ACS",
            "domain": "Cardiovascular",
            "condition": lambda p: ("epigastric" in p.chief_complaint.lower() or "indigestion" in p.chief_complaint.lower() or "fatigue" in p.chief_complaint.lower())
            and (p.vitals.age_category in (AgeCategory.ADULT, AgeCategory.GERIATRIC) or any("diabetes" in h.lower() for h in p.history)),
            "question": "Is there associated diaphoresis, nausea, or radiation to jaw/arm?",
            "impact": "If YES, escalates to ESI 2 (Atypical ACS / Silent MI).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "jaw" in ans.lower() or "sweat" in ans.lower() or "cold" in ans.lower(), 2),
        },
        # 2. Acute Stroke / CVA Mimic
        {
            "id": "VOI-STROKE",
            "domain": "Neurological",
            "condition": lambda p: ("dizziness" in p.chief_complaint.lower() or "imbalance" in p.chief_complaint.lower() or "facial" in p.chief_complaint.lower())
            and (p.vitals.age_category == AgeCategory.GERIATRIC or any("htn" in h.lower() or "hypertension" in h.lower() for h in p.history)),
            "question": "Are there unilateral facial droop, arm drift, or speech changes (FAST criteria)?",
            "impact": "If YES, escalates to ESI 2 (Stroke Alert / CVA).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "droop" in ans.lower() or "drift" in ans.lower() or "slurred" in ans.lower(), 2),
        },
        # 3. DVT / Pulmonary Embolism
        {
            "id": "VOI-DVT-PE",
            "domain": "Vascular/Pulmonary",
            "condition": lambda p: ("calf" in p.chief_complaint.lower() or "leg" in p.chief_complaint.lower() or "flight" in p.chief_complaint.lower() or "breathless" in p.chief_complaint.lower()),
            "question": "Is there unilateral leg swelling or shortness of breath on exertion?",
            "impact": "If YES, escalates to ESI 2 (DVT / Pulmonary Embolism risk).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "swelling" in ans.lower() or "short" in ans.lower(), 2),
        },
        # 4. Decompensated Pediatric Sepsis
        {
            "id": "VOI-PED-SEPSIS",
            "domain": "Pediatric/Infectious",
            "condition": lambda p: p.vitals.age_category == AgeCategory.INFANT and ("fever" in p.chief_complaint.lower() or p.vitals.temp_celsius >= 38.0),
            "question": "Is the infant making wet diapers and maintaining eye contact?",
            "impact": "If NO, escalates to ESI 2 (Decompensated pediatric sepsis).",
            "eval_answer": lambda ans: ("no" in ans.lower() or "poor" in ans.lower() or "lethargic" in ans.lower() or "dry" in ans.lower(), 2),
        },
        # 5. SVT vs Panic / Anxiety Check
        {
            "id": "VOI-SVT-PANIC",
            "domain": "Cardiovascular/Psych",
            "condition": lambda p: ("palpitation" in p.chief_complaint.lower() or "tingling" in p.chief_complaint.lower() or "racing" in p.chief_complaint.lower()),
            "question": "Is there lightheadedness, chest pressure, or a prior history of SVT?",
            "impact": "If YES -> ESI 2/3 (ECG check); If NO -> ESI 4 (Panic / Hyperventilation).",
            "eval_answer": lambda ans: (True, 2 if ("yes" in ans.lower() or "pressure" in ans.lower() or "svt" in ans.lower()) else 4),
        },
        # 6. Pediatric Severe Dehydration / Shock
        {
            "id": "VOI-PED-DEHYDRATION",
            "domain": "Pediatric/Metabolic",
            "condition": lambda p: p.vitals.age_category in (AgeCategory.INFANT, AgeCategory.CHILD) and any(w in p.chief_complaint.lower() for w in ["vomiting", "diarrhea", "intake", "fluid"]),
            "question": "Are tears present when crying, and is capillary refill time under 2 seconds?",
            "impact": "If NO / Delayed, escalates to ESI 2 (Decompensated pediatric dehydration).",
            "eval_answer": lambda ans: ("no" in ans.lower() or "delayed" in ans.lower() or "dry" in ans.lower() or "no tears" in ans.lower(), 2),
        },
        # 7. Acute Surgical Abdomen / Peritonitis
        {
            "id": "VOI-ACUTE-ABDOMEN",
            "domain": "Gastrointestinal/Surgical",
            "condition": lambda p: any(w in p.chief_complaint.lower() for w in ["abdominal", "belly", "stomach", "rlq", "colic"]) and p.vitals.pain_scale >= 6,
            "question": "Is there involuntary guarding, rigidity, or severe pain walking/coughing?",
            "impact": "If YES, escalates to ESI 2 (Acute surgical peritonitis / rupture risk).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "rigid" in ans.lower() or "guard" in ans.lower() or "rebound" in ans.lower(), 2),
        },
        # 8. Anaphylaxis Airway Progression
        {
            "id": "VOI-ANAPHYLAXIS",
            "domain": "Immunologic",
            "condition": lambda p: any(w in p.chief_complaint.lower() for w in ["hives", "rash", "allergy", "bee sting", "swelling"]),
            "question": "Is there any throat tightness, difficulty swallowing, or audible wheeze?",
            "impact": "If YES, escalates to ESI 2 (Evolving Anaphylaxis).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "tight" in ans.lower() or "swallow" in ans.lower() or "wheeze" in ans.lower(), 2),
        },
        # 9. Occult Geriatric Sepsis / Hypoperfusion
        {
            "id": "VOI-OCCULT-SEPSIS",
            "domain": "Geriatric/Infectious",
            "condition": lambda p: p.vitals.age_category == AgeCategory.GERIATRIC and any(w in p.chief_complaint.lower() for w in ["debility", "weakness", "confusion", "off baseline", "shivering"]),
            "question": "Has there been acute change in baseline mental clarity or decreased urinary output?",
            "impact": "If YES, escalates to ESI 2 (qSOFA Occult Sepsis).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "confused" in ans.lower() or "less urine" in ans.lower() or "acute" in ans.lower(), 2),
        },
        # 10. Occult Bleed in Anticoagulated Patient
        {
            "id": "VOI-OCCULT-BLEED",
            "domain": "Hematologic/Vascular",
            "condition": lambda p: bool(p.high_risk_med_alerts) and any(w in p.chief_complaint.lower() for w in ["dizziness", "weak", "fatigue", "faint", "pale"]),
            "question": "Have there been dark/tarry stools, blood in urine, or unexplained bruising?",
            "impact": "If YES, escalates to ESI 2 (Occult internal hemorrhage on anticoagulants).",
            "eval_answer": lambda ans: ("yes" in ans.lower() or "tarry" in ans.lower() or "black" in ans.lower() or "bruis" in ans.lower(), 2),
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

        # Fallback question if no rule matched but confidence remains low
        if not questions:
            questions.append("Can the patient confirm whether symptoms began abruptly and if there is associated syncope or dyspnea?")

        return questions[:2]  # Cap at top 2 targeted questions to prevent nurse cognitive overload

    @classmethod
    def evaluate_response(cls, patient: PatientRecord) -> Tuple[Optional[int], float, List[str]]:
        """
        Calculates adjusted ESI and confidence delta given the nurse's entered answers.
        Returns: (target_esi, confidence_boost, explanation_bullet_points)
        """
        highest_urgency_esi: Optional[int] = None
        total_conf_boost = 0.0
        insights: List[str] = []

        for q, ans in patient.answers_to_followups.items():
            if not ans.strip():
                continue

            matched = False
            for rule in cls.VOI_RULES:
                if rule["question"].strip() == q.strip():
                    matched = True
                    is_positive, recommended_esi = rule["eval_answer"](ans)
                    if is_positive:
                        highest_urgency_esi = (
                            min(highest_urgency_esi, recommended_esi)
                            if highest_urgency_esi is not None
                            else recommended_esi
                        )
                        insights.append(f"VOI Response Trigger ({rule['domain']}): Positive indicator -> Acuity confirmed ESI {recommended_esi}")
                        total_conf_boost += 0.25
                    else:
                        insights.append(f"VOI Response ({rule['domain']}): Negative for high-risk signs -> Acuity ruled stable")
                        total_conf_boost += 0.18
                    break

            if not matched:
                total_conf_boost += 0.15
                insights.append("VOI Response recorded: Clinical ambiguity collapsed")

        return highest_urgency_esi, total_conf_boost, insights