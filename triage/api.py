"""
HL7 FHIR v4 Ingestion Gateway & RiskAssessment Adapter (v2 Pillar 1).
Provides standard interoperability for hospital EHRs, telemetry monitors,
and paramedic tablets with zero-copy translation to internal clinical data contracts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from triage.models import AgeCategory, PatientRecord, TriageResult, Vitals

# Standard HL7 LOINC Codes for Physiological Telemetry
LOINC_CODES = {
    "8867-4": "heart_rate",           # Heart rate in beats/minute
    "8480-6": "systolic_bp",          # Systolic blood pressure in mmHg
    "8462-4": "diastolic_bp",         # Diastolic blood pressure in mmHg
    "9279-1": "resp_rate",            # Respiratory rate in breaths/minute
    "2708-6": "spo2",                 # Oxygen saturation in %
    "59408-5": "spo2",                # Oxygen saturation by pulse oximetry
    "8310-5": "temp_celsius",         # Body temperature in Celsius
    "72514-3": "pain_scale",          # Pain severity score (0-10)
}


class FHIRAdapter:
    """Translates between HL7 FHIR v4 JSON resources and internal domain models."""

    @staticmethod
    def parse_bundle(bundle: Dict[str, Any]) -> PatientRecord:
        """Parses an HL7 FHIR v4 Transaction Bundle into a PatientRecord."""
        patient_id = bundle.get("id", "PT-FHIR-001")
        name = "Unknown Patient"
        age = 40.0
        chief_complaint = "Emergency Department Intake via FHIR"
        history: List[str] = []
        medications: List[str] = []
        allergies: List[str] = []

        # Default standard adult vitals
        v_dict = {
            "age": 40.0,
            "heart_rate": 80,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "resp_rate": 16,
            "spo2": 98.0,
            "temp_celsius": 37.0,
            "pain_scale": 0,
        }

        entries = bundle.get("entry", [])
        for entry in entries:
            res = entry.get("resource", {})
            rtype = res.get("resourceType")

            if rtype == "Patient":
                patient_id = res.get("id", patient_id)
                names = res.get("name", [])
                if names and isinstance(names, list):
                    given = " ".join(names[0].get("given", []))
                    family = names[0].get("family", "")
                    name = f"{given} {family}".strip() or name

                # Compute age from birthDate if present
                bdate_str = res.get("birthDate")
                if bdate_str:
                    try:
                        bdate = datetime.strptime(bdate_str, "%Y-%m-%d")
                        delta_years = (datetime.utcnow() - bdate).days / 365.25
                        age = round(max(0.1, delta_years), 2)
                        v_dict["age"] = age
                    except Exception:
                        pass

                # Extract extensions for medications/allergies if encoded
                for ext in res.get("extension", []):
                    url = ext.get("url", "")
                    if "medication" in url:
                        medications.append(ext.get("valueString", ""))
                    elif "allergy" in url:
                        allergies.append(ext.get("valueString", ""))

            elif rtype == "Observation":
                code_obj = res.get("code", {})
                codings = code_obj.get("coding", [])
                for coding in codings:
                    code = coding.get("code")
                    if code in LOINC_CODES:
                        field_name = LOINC_CODES[code]
                        val_qty = res.get("valueQuantity", {})
                        if "value" in val_qty:
                            raw_val = val_qty["value"]
                            if field_name in ("heart_rate", "systolic_bp", "diastolic_bp", "resp_rate", "pain_scale"):
                                v_dict[field_name] = int(raw_val)
                            else:
                                v_dict[field_name] = float(raw_val)

            elif rtype == "Condition":
                code_text = res.get("code", {}).get("text")
                if code_text:
                    history.append(code_text)

            elif rtype == "Encounter":
                reasons = res.get("reasonCode", [])
                for r in reasons:
                    text = r.get("text")
                    if text:
                        chief_complaint = text

        vitals = Vitals(**v_dict)
        return PatientRecord(
            id=patient_id,
            name=name,
            vitals=vitals,
            chief_complaint=chief_complaint,
            history=history,
            medications=medications,
            allergies=allergies,
        )

    @staticmethod
    def export_risk_assessment(patient: PatientRecord, triage_result: TriageResult) -> Dict[str, Any]:
        """Encapsulates clinical decision into a compliant HL7 FHIR v4 RiskAssessment resource."""
        esi_display_map = {
            1: "Resuscitation (Immediate Life Threat)",
            2: "Emergent (High Risk / Danger Signs)",
            3: "Urgent (Stable Vitals / 2+ Resources)",
            4: "Less Urgent (Stable Vitals / 1 Resource)",
            5: "Non-Urgent (Routine / 0 Resources)",
        }

        return {
            "resourceType": "RiskAssessment",
            "id": f"RA-{patient.pseudo_id}",
            "status": "final",
            "subject": {
                "reference": f"Patient/{patient.pseudo_id}",
                "display": f"Pseudonymized Patient ({patient.vitals.age_category.value.title()})",
            },
            "occurrenceDateTime": datetime.utcnow().isoformat() + "Z",
            "performer": {
                "display": "PatientTriage.ai Algorithmic Core v2"
            },
            "prediction": [
                {
                    "outcome": {
                        "text": f"Emergency Severity Index (ESI) Tier {triage_result.esi_level}"
                    },
                    "probabilityDecimal": triage_result.confidence,
                    "qualitativeRisk": {
                        "coding": [
                            {
                                "system": "http://hl7.org/fhir/sid/esi",
                                "code": str(triage_result.esi_level),
                                "display": esi_display_map.get(triage_result.esi_level, "Acuity Level"),
                            }
                        ]
                    },
                    "rationale": " | ".join(triage_result.explanation),
                }
            ],
            "basis": [
                {"display": risk} for risk in triage_result.primary_risk_factors
            ],
            "note": [
                {"text": exp} for exp in triage_result.explanation
            ],
        }


# Optional FastAPI Integration (Active when FastAPI is installed)
try:
    from fastapi import FastAPI, HTTPException
    from triage.engine import AlgorithmicTriageEngine

    app = FastAPI(
        title="PatientTriage.ai FHIR Gateway",
        version="2.0.0",
        description="HL7 FHIR v4 REST Ingestion & Triage Decision API",
    )
    _engine = AlgorithmicTriageEngine()

    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "PatientTriage.ai FHIR Gateway v2"}

    @app.post("/fhir/v4/Bundle")
    def ingest_bundle(bundle: Dict[str, Any]):
        try:
            patient = FHIRAdapter.parse_bundle(bundle)
            result = _engine.evaluate(patient)
            risk_assessment = FHIRAdapter.export_risk_assessment(patient, result)
            return {
                "patient_pseudo_id": patient.pseudo_id,
                "triage_result": result.model_dump(),
                "fhir_risk_assessment": risk_assessment,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"FHIR parsing error: {str(e)}")

except ImportError:
    app = None
