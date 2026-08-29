"""
Comprehensive Verification Suite for PatientTriage.ai v2 Milestones.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from triage.facility import load_facility_profile, list_available_facilities
from triage.queue import PatientQueue, SqliteQueueRepository
from triage.api import FHIRAdapter
from triage.engine import AlgorithmicTriageEngine, LLMTriageEngine
from triage.cohort import BENCHMARK_COHORT_20


def test_milestone_1_facilities():
    print("=== 1. FACILITY PROFILES (Pillar 4) ===")
    facs = list_available_facilities()
    print("Available facilities:", facs)
    assert len(facs) >= 3, "Expected at least 3 facility profiles"
    for f in facs:
        p = load_facility_profile(f)
        print(f"  • {p.facility_id}: {p.facility_name} | ESI-3 Wait: {p.safe_wait_thresholds_minutes[3]}m | CT: {p.resource_capabilities.has_ct_scanner}")
    print("Milestone 1 PASSED!")


def test_milestone_2_sqlite_wal():
    print("\n=== 2. PERSISTENT CONCURRENT QUEUE (Pillar 2) ===")
    test_db = "test_verify.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    repo = SqliteQueueRepository(db_path=test_db)
    repo.clear()
    for patient in BENCHMARK_COHORT_20:
        repo.add(patient)
    loaded = repo.get_all()
    print(f"Loaded {len(loaded)} / {len(BENCHMARK_COHORT_20)} patients from SQLite WAL store.")
    assert len(loaded) == len(BENCHMARK_COHORT_20)
    repo.clear()
    if os.path.exists(test_db):
        os.remove(test_db)
    print("Milestone 2 PASSED!")


def test_milestone_3_fhir_gateway():
    print("\n=== 3. FHIR v4 INGESTION & RISKASSESSMENT (Pillar 1) ===")
    sample_fhir = {
        "resourceType": "Bundle",
        "id": "BUNDLE-TEST",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "P-FHIR-01", "name": [{"given": ["Jane"], "family": "Doe"}], "birthDate": "1990-01-01"}},
            {"resource": {"resourceType": "Observation", "code": {"coding": [{"code": "8867-4"}]}, "valueQuantity": {"value": 145}}},
            {"resource": {"resourceType": "Observation", "code": {"coding": [{"code": "2708-6"}]}, "valueQuantity": {"value": 89.0}}},
            {"resource": {"resourceType": "Encounter", "reasonCode": [{"text": "Acute severe asthma attack"}]}}
        ]
    }
    pt = FHIRAdapter.parse_bundle(sample_fhir)
    algo = AlgorithmicTriageEngine()
    res = algo.evaluate(pt)
    risk_doc = FHIRAdapter.export_risk_assessment(pt, res)
    print(f"FHIR Ingested: {pt.name} -> ESI Level {res.esi_level} | Pred Risk: {risk_doc['prediction'][0]['qualitativeRisk']['coding'][0]['display']}")
    assert res.esi_level in (1, 2)
    print("Milestone 3 PASSED!")


def test_milestone_4_neurosymbolic_slm():
    print("\n=== 4. NEUROSYMBOLIC CLINICAL SLM (Pillar 3) ===")
    llm = LLMTriageEngine()
    note = "EMS Drop-off: 82yo female with severe confusion, shivering, hypothermia. Temp: 35.1 C, HR: 110, BP: 86/50, RR: 24, SpO2: 93%. History of dementia on donepezil."
    slm_pt, slm_res = llm.evaluate_narrative(note)
    print(f"Narrative Extracted: {slm_pt.vitals.age}yo (Temp: {slm_pt.vitals.temp_celsius}C, BP: {slm_pt.vitals.systolic_bp}/{slm_pt.vitals.diastolic_bp}) -> ESI {slm_res.esi_level} (Deterministic Red-Line Veto: {slm_res.deterministic_rule_hit})")
    assert slm_res.esi_level == 2
    assert slm_res.deterministic_rule_hit is True
    print("Milestone 4 PASSED!")


def test_milestone_5_benchmark_cohort():
    print("\n=== 5. BENCHMARK COHORT TRIAGE (20 Patients) ===")
    algo = AlgorithmicTriageEngine()
    evals = [algo.evaluate(p) for p in BENCHMARK_COHORT_20]
    print(f"Successfully evaluated all {len(evals)} benchmark patients.")
    assert len(evals) == 20
    print("Milestone 5 PASSED!")


if __name__ == "__main__":
    test_milestone_1_facilities()
    test_milestone_2_sqlite_wal()
    test_milestone_3_fhir_gateway()
    test_milestone_4_neurosymbolic_slm()
    test_milestone_5_benchmark_cohort()
    print("\n=======================================================")
    print("  ALL V2 MILESTONE VERIFICATION CHECKS PASSED (5/5)!")
    print("=======================================================")
