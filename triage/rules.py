"""
Declarative Physiological Red-Lines and Age-Stratified Thresholds.
Calibrated against Pediatric Early Warning Score (PEWS), NEWS2, and qSOFA protocols.
v1 includes structured High-Risk Medication Profiling & Critical Syndrome Safety Stops.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from triage.models import AgeCategory, PatientRecord, Vitals


@dataclass(frozen=True)
class AgeVitalThresholds:
    normal_hr: Tuple[int, int]
    critical_hr: Tuple[int, int]
    normal_rr: Tuple[int, int]
    critical_rr: Tuple[int, int]
    normal_sbp: Tuple[int, int]
    critical_sbp_min: int
    critical_sbp_max: Optional[int]
    fever_temp: float
    critical_temp_high: float
    critical_temp_low: Optional[float]
    critical_spo2: float


AGE_THRESHOLDS = {
    AgeCategory.INFANT: AgeVitalThresholds(
        normal_hr=(100, 160), critical_hr=(80, 180),
        normal_rr=(30, 50), critical_rr=(20, 60),
        normal_sbp=(70, 100), critical_sbp_min=70, critical_sbp_max=None,
        fever_temp=38.0, critical_temp_high=38.5, critical_temp_low=None,
        critical_spo2=94.0,
    ),
    AgeCategory.CHILD: AgeVitalThresholds(
        normal_hr=(70, 120), critical_hr=(60, 140),
        normal_rr=(18, 30), critical_rr=(14, 40),
        normal_sbp=(85, 115), critical_sbp_min=80, critical_sbp_max=None,
        fever_temp=38.3, critical_temp_high=39.0, critical_temp_low=None,
        critical_spo2=93.0,
    ),
    AgeCategory.ADULT: AgeVitalThresholds(
        normal_hr=(60, 100), critical_hr=(50, 120),
        normal_rr=(12, 20), critical_rr=(10, 28),
        normal_sbp=(100, 140), critical_sbp_min=90, critical_sbp_max=190,
        fever_temp=38.3, critical_temp_high=39.5, critical_temp_low=None,
        critical_spo2=92.0,
    ),
    AgeCategory.GERIATRIC: AgeVitalThresholds(
        normal_hr=(60, 90), critical_hr=(50, 105),
        normal_rr=(12, 20), critical_rr=(10, 26),
        normal_sbp=(110, 145), critical_sbp_min=95, critical_sbp_max=190,
        fever_temp=37.8, critical_temp_high=38.5, critical_temp_low=35.5,
        critical_spo2=91.0,
    ),
}


class RuleRegistry:
    """Evaluates physiological boundaries and danger signs."""

    @staticmethod
    def evaluate_vitals(vitals: Vitals) -> Tuple[bool, List[str], int]:
        category = vitals.age_category
        t = AGE_THRESHOLDS[category]
        risks: List[str] = []
        is_critical = False
        esi_target = 3

        if vitals.spo2 < t.critical_spo2:
            is_critical = True
            risks.append(f"Critical Hypoxemia: SpO2 {vitals.spo2}% (<{t.critical_spo2}%)")
            esi_target = min(esi_target, 2 if vitals.spo2 >= 88.0 else 1)

        crit_min_hr, crit_max_hr = t.critical_hr
        if vitals.heart_rate > crit_max_hr:
            is_critical = True
            risks.append(f"Severe Tachycardia: HR {vitals.heart_rate} bpm (>{crit_max_hr})")
            esi_target = min(esi_target, 2)
        elif vitals.heart_rate < crit_min_hr:
            is_critical = True
            risks.append(f"Severe Bradycardia: HR {vitals.heart_rate} bpm (<{crit_min_hr})")
            esi_target = min(esi_target, 2)

        crit_min_rr, crit_max_rr = t.critical_rr
        if vitals.resp_rate > crit_max_rr:
            is_critical = True
            risks.append(f"Severe Tachypnea: RR {vitals.resp_rate} bpm (>{crit_max_rr})")
            esi_target = min(esi_target, 2)
        elif vitals.resp_rate < crit_min_rr:
            is_critical = True
            risks.append(f"Severe Bradypnea: RR {vitals.resp_rate} bpm (<{crit_min_rr})")
            esi_target = min(esi_target, 2)

        if vitals.systolic_bp < t.critical_sbp_min:
            is_critical = True
            risks.append(f"Decompensated Hypotension: SBP {vitals.systolic_bp} mmHg (<{t.critical_sbp_min})")
            esi_target = min(esi_target, 2)
        elif t.critical_sbp_max and vitals.systolic_bp > t.critical_sbp_max:
            is_critical = True
            risks.append(f"Hypertensive Crisis: SBP {vitals.systolic_bp} mmHg (>{t.critical_sbp_max})")
            esi_target = min(esi_target, 2)

        if t.critical_temp_low and vitals.temp_celsius < t.critical_temp_low:
            is_critical = True
            risks.append(f"Occult Hypothermia / Geriatric Sepsis: Temp {vitals.temp_celsius}°C (<{t.critical_temp_low}°C)")
            esi_target = min(esi_target, 2)
        elif vitals.temp_celsius >= t.critical_temp_high:
            is_critical = True
            risks.append(f"Hyperpyrexia: Temp {vitals.temp_celsius}°C (>={t.critical_temp_high}°C)")
            esi_target = min(esi_target, 2)

        return is_critical, risks, esi_target

    @staticmethod
    def evaluate_clinical_syndromes(patient: PatientRecord) -> Tuple[bool, List[str], Optional[int]]:
        complaint_lower = patient.chief_complaint.lower()
        history_lower = [h.lower() for h in patient.history]
        meds_lower = [m.lower() for m in patient.medications]
        all_hx_meds = " ".join(history_lower + meds_lower)
        
        risks: List[str] = []
        esi_target: Optional[int] = None
        hit = False

        # Pediatric Airway Threat
        if patient.vitals.age_category in (AgeCategory.INFANT, AgeCategory.CHILD):
            if any(w in complaint_lower for w in ["stridor", "barking cough", "drooling", "lethargy", "sunken fontanelle"]):
                hit = True
                risks.append("Pediatric Airway / Metabolic Threat (Impending Decompensation)")
                esi_target = 2

        # Acute Meningitis / Nuchal Rigidity
        if any(w in complaint_lower for w in ["neck stiffness", "photophobia", "violent headache", "nuchal rigidity"]):
            if patient.vitals.temp_celsius >= 38.0:
                hit = True
                risks.append("Acute Meningitis Red Flag (Fever + Meningismus)")
                esi_target = 2

        # Tearing Pain (AAA / Aortic Dissection)
        if ("tearing" in complaint_lower or "ripping" in complaint_lower) and ("back" in complaint_lower or "chest" in complaint_lower):
            hit = True
            risks.append("Vascular Catastrophe: Tearing pain (Suspected Dissection/AAA)")
            esi_target = 1 if patient.vitals.systolic_bp < 90 else 2

        # High-Risk Medication Profiling (Anticoagulants / DOACs + Head/Trauma)
        has_anticoagulant = any(a in all_hx_meds for a in ["warfarin", "eliquis", "xarelto", "coumadin", "apixaban", "blood thinner", "heparin"])
        if ("fall" in complaint_lower or "head" in complaint_lower or "trauma" in complaint_lower or "hit" in complaint_lower):
            if has_anticoagulant:
                hit = True
                risks.append("High-Risk Trauma on Anticoagulation (Intracranial Bleed Risk)")
                esi_target = 2
            elif patient.vitals.age_category == AgeCategory.GERIATRIC:
                risks.append("Geriatric Fall / Trauma Risk (Potential Occult Bleed)")

        # Immunocompromised Fever Alert
        has_immunosuppression = any(im in all_hx_meds for im in ["chemotherapy", "prednisone", "methotrexate", "tacrolimus", "transplant", "cancer"])
        if has_immunosuppression and patient.vitals.temp_celsius >= 38.0:
            hit = True
            risks.append("Neutropenic / Immunocompromised Fever Alert (High Sepsis Mortality Risk)")
            esi_target = 2

        # Anaphylaxis vs Simple Urticaria Progression Check
        if ("hive" in complaint_lower or "rash" in complaint_lower or "allergic" in complaint_lower):
            if any(w in complaint_lower for w in ["lip", "tongue", "throat", "dyspnea", "wheeze", "swallowing"]):
                hit = True
                risks.append("Acute Anaphylaxis Red-Line (Airway / Respiratory Involvement)")
                esi_target = 2

        # Upper Airway Threat
        if ("drooling" in complaint_lower or "muffled voice" in complaint_lower) and "throat" in complaint_lower:
            hit = True
            risks.append("Upper Airway Threat (Peritonsillar Abscess / Epiglottitis)")
            esi_target = 2

        # High-Risk Meds Summary Alert
        for med_alert in patient.high_risk_med_alerts:
            risks.append(f"Medication Alert: {med_alert}")

        return hit, risks, esi_target


def evaluate_red_lines(patient: PatientRecord) -> Tuple[bool, List[str], int]:
    vital_hit, vital_risks, vital_esi = RuleRegistry.evaluate_vitals(patient.vitals)
    syndrome_hit, syndrome_risks, syndrome_esi = RuleRegistry.evaluate_clinical_syndromes(patient)

    all_risks = vital_risks + syndrome_risks
    hit = vital_hit or syndrome_hit

    target_esi = 5
    if vital_hit:
        target_esi = min(target_esi, vital_esi)
    if syndrome_hit and syndrome_esi:
        target_esi = min(target_esi, syndrome_esi)

    if not hit:
        target_esi = 3

    return hit, all_risks, target_esi