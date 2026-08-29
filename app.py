"""
PatientTriage.ai — Clinical Decision Support HUD (v2 Polished & Responsive).
Features:
- Visual-first clinical command center with dynamic vital alert highlights and acuity distributions.
- Workstation 1: Real-time Intake & Neurosymbolic SLM Triage with 1-click VOI response pills & EMS note parser.
- Workstation 2: Dynamic Deterioration Radar with Concurrent SQLite WAL Persistence & Vital Velocity.
- Workstation 3: Immutable Regulatory Audit Stream (HIPAA Safe Harbor SHA-256) & FHIR v4 Gateway Sandbox.
"""

import json
import streamlit as st
import pandas as pd
from datetime import datetime
from triage.models import AgeCategory, PatientRecord, Vitals
from triage.engine import AlgorithmicTriageEngine, LLMTriageEngine, SLMEntityExtractor
from triage.facility import FacilityProfile, list_available_facilities, load_facility_profile
from triage.queue import PatientQueue, SqliteQueueRepository
from triage.audit import AuditLogger
from triage.api import FHIRAdapter
from triage.cohort import load_benchmark_cohort

# Page Configuration
st.set_page_config(
    page_title="PatientTriage.ai | Clinical HUD",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Enterprise Clinical Dashboard Styling
st.markdown("""
<style>
    /* Global Layout & Font Tweaks */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        padding-left: 1.6rem;
        padding-right: 1.6rem;
        max-width: 100%;
    }

    /* Responsive KPI Metric Grid */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-bottom: 18px;
    }
    
    .kpi-card {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 16px 18px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 110px;
        box-sizing: border-box;
        transition: border-color 0.2s ease;
    }
    .kpi-card:hover {
        border-color: rgba(255, 255, 255, 0.25);
    }
    
    .kpi-label {
        font-size: 11px;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 600;
        margin-bottom: 2px;
    }
    
    .kpi-val {
        font-size: 26px;
        font-weight: 800;
        line-height: 1.2;
        color: #F8FAFC;
        font-variant-numeric: tabular-nums;
    }
    
    .kpi-sub {
        font-size: 12px;
        font-weight: 500;
        margin-top: 4px;
        color: #94A3B8;
    }
    
    .kpi-sub.alert { color: #F87171; font-weight: 600; }
    .kpi-sub.warn { color: #FBBF24; font-weight: 600; }
    .kpi-sub.ok { color: #34D399; }

    /* Responsive Vitals Strip Grid */
    .vitals-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 12px;
        margin: 14px 0 20px 0;
    }
    
    .vital-box {
        background-color: rgba(255, 255, 255, 0.025);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 12px 10px;
        text-align: center;
        min-height: 84px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    
    .vital-box.abnormal {
        background-color: rgba(239, 68, 68, 0.12);
        border: 1px solid #EF4444;
    }
    
    .vital-box.warning {
        background-color: rgba(245, 158, 11, 0.12);
        border: 1px solid #F59E0B;
    }
    
    .vital-label {
        font-size: 11px;
        color: #94A3B8;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    
    .vital-val {
        font-size: 22px;
        font-weight: 800;
        color: #F8FAFC;
        margin-top: 2px;
        font-variant-numeric: tabular-nums;
    }
    
    .vital-status-tag {
        font-size: 9px;
        text-transform: uppercase;
        font-weight: 700;
        margin-top: 2px;
        letter-spacing: 0.5px;
    }
    .vital-status-tag.crit { color: #FCA5A5; }
    .vital-status-tag.warn { color: #FCD34D; }

    /* Acuity Distribution Bar */
    .acuity-bar-container {
        display: flex;
        width: 100%;
        height: 12px;
        border-radius: 6px;
        overflow: hidden;
        margin: 12px 0 16px 0;
        background-color: rgba(255, 255, 255, 0.05);
    }
    
    /* Media Queries for Screen Responsiveness */
    @media (max-width: 1024px) {
        .kpi-grid { grid-template-columns: repeat(2, 1fr); }
        .vitals-grid { grid-template-columns: repeat(3, 1fr); }
    }

    @media (max-width: 640px) {
        .kpi-grid { grid-template-columns: 1fr; }
        .vitals-grid { grid-template-columns: repeat(2, 1fr); }
    }

    hr {
        margin: 16px 0;
        border: 0;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Session State Singletons
if "engine" not in st.session_state:
    st.session_state.engine = AlgorithmicTriageEngine()
if "llm_engine" not in st.session_state:
    st.session_state.llm_engine = LLMTriageEngine()
if "queue" not in st.session_state:
    queue = PatientQueue(repo=SqliteQueueRepository())
    existing = queue.repo.get_all()
    if not existing:
        for p in load_benchmark_cohort():
            res = st.session_state.engine.evaluate(p)
            p.assigned_esi = res.esi_level
            queue.repo.add(p)
    st.session_state.queue = queue
if "audit_logger" not in st.session_state:
    st.session_state.audit_logger = AuditLogger()
if "clinician_id" not in st.session_state:
    st.session_state.clinician_id = "RN-4402"

# Sidebar Telemetry & Facility Profiler
st.sidebar.markdown("### Facility Configuration")
available_facs = list_available_facilities()
fac_labels = {
    "community_hospital": "Community General Hospital",
    "level1_trauma": "Metropolitan Level 1 Trauma Center",
    "rural_critical_access": "Pine Creek Critical Access Hospital",
}
selected_fac_id = st.sidebar.selectbox(
    "Active Facility Profile",
    available_facs,
    index=0,
    format_func=lambda fid: fac_labels.get(fid, fid.replace("_", " ").title())
)
active_facility = load_facility_profile(selected_fac_id)
st.session_state.queue.set_facility(active_facility)

st.sidebar.markdown(f"**Facility Tier:** `{active_facility.tier}`")
col_fac1, col_fac2 = st.sidebar.columns(2)
col_fac1.markdown(f"CT Scanner: **{'Available' if active_facility.resource_capabilities.has_ct_scanner else 'None'}**")
col_fac2.markdown(f"Cath Lab: **{'Available' if active_facility.resource_capabilities.has_cath_lab else 'None'}**")

st.sidebar.divider()
st.sidebar.markdown("### System Telemetry")
st.sidebar.markdown(f"Clinician ID: `{st.session_state.clinician_id}`")
st.sidebar.markdown("Engine: `Neurosymbolic v2 (<1ms)`")
st.sidebar.markdown("Queue Store: `SQLite WAL (Active)`")
st.sidebar.markdown("Privacy: `HIPAA Safe Harbor SHA-256`")

st.sidebar.divider()
st.sidebar.markdown("### Department Controls")
surge_toggle = st.sidebar.toggle("3x Surge Mode", value=st.session_state.queue.surge_mode)
st.session_state.queue.surge_mode = surge_toggle

col_sb1, col_sb2 = st.sidebar.columns(2)
if col_sb1.button("Advance +15m", use_container_width=True):
    st.session_state.queue.simulate_time_advance(15)
    st.rerun()

if col_sb2.button("Reset Benchmark", use_container_width=True):
    st.session_state.queue.repo.clear()
    for p in load_benchmark_cohort():
        res = st.session_state.engine.evaluate(p)
        p.assigned_esi = res.esi_level
        st.session_state.queue.repo.add(p)
    st.rerun()

# Global Telemetry Computation
all_patients = st.session_state.queue.repo.get_all()
breached_count = sum(1 for p in all_patients if st.session_state.queue.is_breach(p))
decompensating_count = sum(1 for p in all_patients if PatientQueue.calculate_vital_velocity_penalty(p) > 0)
occupancy_pct = "96%" if surge_toggle else "78%"
occupancy_sub = "Critical Surge Capacity" if surge_toggle else "Nominal Capacity"
dept_status = "SURGE ACTIVE" if surge_toggle else "NOMINAL"
dept_sub = "3x Load Balancing" if surge_toggle else "Standard Flow"

# Responsive Header KPI Grid
st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi-card">
        <div class="kpi-label">Department Status</div>
        <div class="kpi-val" style="color: {'#F87171' if surge_toggle else '#F8FAFC'};">{dept_status}</div>
        <div class="kpi-sub {'warn' if surge_toggle else 'ok'}">{dept_sub}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Occupancy Capacity</div>
        <div class="kpi-val">{occupancy_pct}</div>
        <div class="kpi-sub {'alert' if surge_toggle else 'ok'}">{occupancy_sub}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Patients Waiting</div>
        <div class="kpi-val">{len(all_patients)}</div>
        <div class="kpi-sub {'alert' if decompensating_count else 'ok'}">{'Deterioration Detected: ' + str(decompensating_count) if decompensating_count else 'All Vitals Stable'}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Re-Triage Breaches ({active_facility.facility_name[:14]})</div>
        <div class="kpi-val" style="color: {'#F87171' if breached_count else '#F8FAFC'};">{breached_count}</div>
        <div class="kpi-sub {'alert' if breached_count else 'ok'}">{'Action Required' if breached_count else 'Within Safe Windows'}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Tab Workstations
tab_intake, tab_radar, tab_audit = st.tabs([
    "Intake & Neurosymbolic Scorer",
    "Waiting Room Deterioration Radar",
    "FHIR v4 Bridge & Immutable Audit Ledger",
])

# -------------------------------------------------------------
# WORKSTATION 1: INTAKE & NEUROSYMBOLIC SCORER
# -------------------------------------------------------------
with tab_intake:
    # Free-Text Paramedic Ingestion Drawer
    with st.expander("Paramedic Run-Sheet & Free-Text Note Ingestion (Clinical SLM)", expanded=False):
        st.markdown("Paste unstructured EMS radio report or select a preset clinical scenario:")
        
        sample_presets = {
            "Custom Free-Text": "",
            "Acute Stroke / CVA on Warfarin": "Paramedic report: 73yo male found slumped on kitchen floor with sudden left facial droop and slurred speech. HR: 112 bpm, BP: 175/95, RR: 20, SpO2: 94%, Temp: 36.8C, Pain: 4/10. Patient has history of hypertension and taking Warfarin daily.",
            "Pediatric Respiratory Distress": "EMS: 4yo female presenting with severe barking cough, inspiratory stridor, and intercostal retractions. Pulse 155, RR 42, SpO2 91% on room air, Temp 38.6C. History of reactive airway disease.",
            "Geriatric Occult Sepsis": "Nursing home drop-off: 84yo female presenting with shivering, altered baseline sensorium, and low oral intake. HR: 108, BP: 86/48, RR: 24, SpO2: 93%, Core Temp: 35.1C. History of dementia.",
        }
        chosen_preset = st.selectbox("Select EMS Narrative Preset", list(sample_presets.keys()))
        default_val = sample_presets[chosen_preset] if sample_presets[chosen_preset] else "Paramedic report: 68yo male with sudden tearing mid-chest pain radiating to shoulder blades. HR: 116, BP: 88/50, RR: 26, SpO2: 94%, Temp: 36.5C, Pain: 10/10."
        free_text_input = st.text_area("Triage Free-Text Narrative", value=default_val, height=85)
        
        if st.button("Parse Note with Clinical SLM & Add to Queue", use_container_width=True):
            parsed_patient, slm_result = st.session_state.llm_engine.evaluate_narrative(free_text_input)
            parsed_patient.assigned_esi = slm_result.esi_level
            st.session_state.queue.repo.add(parsed_patient)
            st.success(f"Parsed narrative for {parsed_patient.name} ({parsed_patient.pseudo_id}) -> Assigned ESI {slm_result.esi_level}!")
            st.rerun()

    col_sel1, col_sel2 = st.columns([3, 1])
    patient_names = [f"{p.id} | {p.pseudo_id} -- {p.name} ({p.vitals.age_category.value.title()}, {p.vitals.age:.1f}y)" for p in all_patients]
    selected_idx = col_sel1.selectbox("Select Patient from Intake / Waiting Fleet", range(len(patient_names)), format_func=lambda i: patient_names[i])
    current_patient = all_patients[selected_idx]

    col_sel2.markdown(f"""
    <div style="background-color:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:10px 14px; text-align:right;">
        <span style="font-size:11px; color:#94A3B8; text-transform:uppercase; font-weight:600;">HIPAA Token</span><br>
        <span style="font-size:15px; font-weight:700; font-family:monospace; color:#E2E8F0;">{current_patient.pseudo_id}</span>
    </div>
    """, unsafe_allow_html=True)

    # Active Clinical Alerts
    if current_patient.high_risk_med_alerts:
        alert_str = " | ".join(current_patient.high_risk_med_alerts)
        st.markdown(f"""
        <div style="background-color:rgba(239,68,68,0.15); border-left:4px solid #EF4444; padding:8px 12px; border-radius:4px; margin-bottom:12px; font-size:13px; color:#FCA5A5;">
            <strong>HIGH-RISK MEDICATION ALERT:</strong> {alert_str}
        </div>
        """, unsafe_allow_html=True)

    # Dynamic Vitals Classification
    v = current_patient.vitals
    hr_crit = v.heart_rate > 130 or v.heart_rate < 50
    bp_crit = v.systolic_bp < 90 or v.systolic_bp > 190
    rr_crit = v.resp_rate > 28 or v.resp_rate < 10
    spo2_crit = v.spo2 < 92.0
    temp_warn = v.temp_celsius >= 38.5 or v.temp_celsius < 35.5
    pain_warn = v.pain_scale >= 7

    st.markdown(f"""
    <div class="vitals-grid">
        <div class="vital-box {'abnormal' if hr_crit else ''}">
            <div class="vital-label">Heart Rate</div>
            <div class="vital-val">{v.heart_rate} <span style="font-size:12px; font-weight:400; color:#94A3B8;">bpm</span></div>
            <div class="vital-status-tag {'crit' if hr_crit else ''}">{'CRITICAL' if hr_crit else 'NORMAL'}</div>
        </div>
        <div class="vital-box {'abnormal' if bp_crit else ''}">
            <div class="vital-label">Blood Pressure</div>
            <div class="vital-val">{v.systolic_bp}/{v.diastolic_bp}</div>
            <div class="vital-status-tag {'crit' if bp_crit else ''}">{'CRITICAL' if bp_crit else 'NORMAL'}</div>
        </div>
        <div class="vital-box {'abnormal' if rr_crit else ''}">
            <div class="vital-label">Resp Rate</div>
            <div class="vital-val">{v.resp_rate} <span style="font-size:12px; font-weight:400; color:#94A3B8;">/min</span></div>
            <div class="vital-status-tag {'crit' if rr_crit else ''}">{'CRITICAL' if rr_crit else 'NORMAL'}</div>
        </div>
        <div class="vital-box {'abnormal' if spo2_crit else ''}">
            <div class="vital-label">SpO2</div>
            <div class="vital-val">{v.spo2:.0f}%</div>
            <div class="vital-status-tag {'crit' if spo2_crit else ''}">{'HYPOXIC' if spo2_crit else 'OPTIMAL'}</div>
        </div>
        <div class="vital-box {'warning' if temp_warn else ''}">
            <div class="vital-label">Core Temp</div>
            <div class="vital-val">{v.temp_celsius:.1f}°C</div>
            <div class="vital-status-tag {'warn' if temp_warn else ''}">{'FEVER / HYPO' if temp_warn else 'EU-THERMIC'}</div>
        </div>
        <div class="vital-box {'warning' if pain_warn else ''}">
            <div class="vital-label">Pain Score</div>
            <div class="vital-val">{v.pain_scale}/10</div>
            <div class="vital-status-tag {'warn' if pain_warn else ''}">{'SEVERE' if pain_warn else 'MILD-MOD'}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Evaluate Patient
    result = st.session_state.engine.evaluate(current_patient)
    current_patient.assigned_esi = result.esi_level
    st.session_state.queue.repo.update(current_patient)

    # Primary Decision Presentation
    col_dec1, col_dec2 = st.columns([1, 2])

    with col_dec1:
        esi_color_map = {
            1: ("#B71C1C", "Resuscitation (Immediate Life Threat)"),
            2: ("#E65100", "Emergent (High Risk / Danger Signs)"),
            3: ("#F57F17", "Urgent (Stable / Multiple Resources)"),
            4: ("#2E7D32", "Less Urgent (Stable / Single Resource)"),
            5: ("#1565C0", "Non-Urgent (Routine Exam / 0 Resources)"),
        }
        bg_col, esi_title = esi_color_map.get(result.esi_level, ("#333", "Acuity Level"))

        st.markdown(f"""
        <div style="background-color:{bg_col}; padding:20px; border-radius:8px; color:white; text-align:center; box-shadow:0 4px 6px -1px rgba(0,0,0,0.3);">
            <div style="font-size:12px; text-transform:uppercase; letter-spacing:1px; font-weight:600; opacity:0.9;">Triage Recommendation</div>
            <div style="font-size:44px; font-weight:800; line-height:1.1; margin:8px 0;">ESI LEVEL {result.esi_level}</div>
            <div style="font-size:13px; font-weight:600; opacity:0.95;">{esi_title}</div>
            <div style="margin-top:14px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.2); font-size:14px;">
                Confidence: <strong>{int(result.confidence * 100)}%</strong> ({'High' if result.confidence >= 0.85 else 'Calibrated Medium' if result.confidence >= 0.70 else 'Uncertain / Escalated'})
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Clinician Override Management", expanded=(current_patient.override_esi is not None)):
            new_override = st.selectbox("Override ESI Level", [None, 1, 2, 3, 4, 5], index=0 if current_patient.override_esi is None else current_patient.override_esi)
            override_justification = st.text_input("Mandatory Justification Rationale", value=current_patient.override_reason or "", placeholder="e.g. Observed severe diaphoresis / abnormal pallor")
            
            if st.button("Commit Final Triage Decision", use_container_width=True):
                if new_override is not None and new_override != result.esi_level and not override_justification.strip():
                    st.error("Regulatory Requirement: Clinical rationale required for manual override.")
                else:
                    current_patient.override_esi = new_override
                    current_patient.override_reason = override_justification if new_override else None
                    st.session_state.queue.repo.update(current_patient)
                    st.session_state.audit_logger.log_assessment(
                        patient=current_patient,
                        ai_result=result,
                        clinician_id=st.session_state.clinician_id,
                        override_esi=new_override,
                        override_reason=override_justification,
                    )
                    st.success("Triage event committed to audit ledger.")
                    st.rerun()

    with col_dec2:
        st.markdown("#### Clinical Findings & Diagnostic Rationale")
        st.markdown(f"**Presenting Complaint:** *{current_patient.chief_complaint}*")
        
        for item in result.explanation:
            st.markdown(f"-- {item}")

        # Active Value of Information (VOI) Assistant with 1-Click Action Pills
        if result.is_ambiguous and result.recommended_followups:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <div style="background-color:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); border-radius:6px; padding:12px;">
                <div style="color:#FBBF24; font-weight:700; font-size:12px; text-transform:uppercase; margin-bottom:4px;">Active Value-of-Information (VOI) Assistant</div>
                <div style="font-size:12px; color:#D1D5DB;">Epistemic diagnostic entropy detected. Answer targeted query to collapse uncertainty:</div>
            </div>
            """, unsafe_allow_html=True)

            for q in result.recommended_followups:
                st.markdown(f"**Targeted Question:** `{q}`")
                
                # 1-Click Fast Response Pills
                col_p1, col_p2, col_p3 = st.columns([1, 1, 2])
                if col_p1.button("Positive (High Risk)", key=f"p_pos_{q}", use_container_width=True):
                    current_patient.answers_to_followups[q] = "Yes, positive high risk indicator observed"
                    st.session_state.queue.repo.update(current_patient)
                    st.rerun()
                if col_p2.button("Negative (Ruled Out)", key=f"p_neg_{q}", use_container_width=True):
                    current_patient.answers_to_followups[q] = "No, negative for danger sign"
                    st.session_state.queue.repo.update(current_patient)
                    st.rerun()
                    
                ans_text = col_p3.text_input("Or type detail:", value=current_patient.answers_to_followups.get(q, ""), key=f"q_{q}")
                if ans_text and ans_text != current_patient.answers_to_followups.get(q, ""):
                    current_patient.answers_to_followups[q] = ans_text
                    st.session_state.queue.repo.update(current_patient)
                    st.rerun()

    # Progressive Disclosure: Full Intake Record Editor
    with st.expander("Expand Intake Record Editor (History, Medications, Allergies, Raw Vitals)"):
        ec1, ec2 = st.columns(2)
        v_complaint = ec1.text_input("Primary Chief Complaint", current_patient.chief_complaint)
        v_hx = ec2.text_input("Past Medical History (comma-separated)", ", ".join(current_patient.history))
        v_meds = ec1.text_input("Home Medications (comma-separated)", ", ".join(current_patient.medications))
        v_all = ec2.text_input("Documented Allergies (comma-separated)", ", ".join(current_patient.allergies))
        
        vc1, vc2, vc3, vc4 = st.columns(4)
        v_hr = vc1.number_input("Heart Rate", 20, 260, current_patient.vitals.heart_rate)
        v_sbp = vc2.number_input("Systolic BP", 30, 260, current_patient.vitals.systolic_bp)
        v_dbp = vc3.number_input("Diastolic BP", 20, 160, current_patient.vitals.diastolic_bp)
        v_rr = vc4.number_input("Resp Rate", 6, 80, current_patient.vitals.resp_rate)
        
        vc5, vc6, vc7, vc8 = st.columns(4)
        v_spo2 = vc5.number_input("SpO2 %", 50.0, 100.0, float(current_patient.vitals.spo2), step=1.0)
        v_temp = vc6.number_input("Temp C", 28.0, 43.0, float(current_patient.vitals.temp_celsius), step=0.1)
        v_pain = vc7.slider("Pain (0-10)", 0, 10, current_patient.vitals.pain_scale)
        v_age = vc8.number_input("Age Years", 0.1, 120.0, float(current_patient.vitals.age), step=0.1)

        if st.button("Save Record Edits"):
            current_patient.vitals = Vitals(
                age=v_age, heart_rate=v_hr, systolic_bp=v_sbp, diastolic_bp=v_dbp,
                resp_rate=v_rr, spo2=v_spo2, temp_celsius=v_temp, pain_scale=v_pain,
            )
            current_patient.chief_complaint = v_complaint
            current_patient.history = [h.strip() for h in v_hx.split(",") if h.strip()]
            current_patient.medications = [m.strip() for m in v_meds.split(",") if m.strip()]
            current_patient.allergies = [a.strip() for a in v_all.split(",") if a.strip()]
            st.session_state.queue.repo.update(current_patient)
            st.success("Record saved.")
            st.rerun()

# -------------------------------------------------------------
# WORKSTATION 2: WAITING ROOM DETERIORATION RADAR
# -------------------------------------------------------------
with tab_radar:
    main_q, fast_q = st.session_state.queue.get_ranked_queues()

    # Acuity Breakdown Visual Bar
    esi_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for p in all_patients:
        eff_esi = p.effective_esi or 3
        esi_counts[eff_esi] = esi_counts.get(eff_esi, 0) + 1
    
    total_pts = len(all_patients) or 1
    pct_1 = (esi_counts[1] / total_pts) * 100
    pct_2 = (esi_counts[2] / total_pts) * 100
    pct_3 = (esi_counts[3] / total_pts) * 100
    pct_4 = (esi_counts[4] / total_pts) * 100
    pct_5 = (esi_counts[5] / total_pts) * 100

    st.markdown("#### Waiting Fleet Acuity Distribution")
    st.markdown(f"""
    <div class="acuity-bar-container">
        <div style="width:{pct_1}%; background-color:#B71C1C;" title="ESI 1: {esi_counts[1]}"></div>
        <div style="width:{pct_2}%; background-color:#E65100;" title="ESI 2: {esi_counts[2]}"></div>
        <div style="width:{pct_3}%; background-color:#F57F17;" title="ESI 3: {esi_counts[3]}"></div>
        <div style="width:{pct_4}%; background-color:#2E7D32;" title="ESI 4: {esi_counts[4]}"></div>
        <div style="width:{pct_5}%; background-color:#1565C0;" title="ESI 5: {esi_counts[5]}"></div>
    </div>
    <div style="display:flex; justify-content:space-between; font-size:11px; color:#94A3B8; font-weight:600; text-transform:uppercase;">
        <span><span style="color:#F87171;">ESI 1 (Resus):</span> {esi_counts[1]}</span>
        <span><span style="color:#FB923C;">ESI 2 (Emergent):</span> {esi_counts[2]}</span>
        <span><span style="color:#FACC15;">ESI 3 (Urgent):</span> {esi_counts[3]}</span>
        <span><span style="color:#4ADE80;">ESI 4 (Less Urgent):</span> {esi_counts[4]}</span>
        <span><span style="color:#60A5FA;">ESI 5 (Non-Urgent):</span> {esi_counts[5]}</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    def build_clean_queue_df(queue_items):
        data = []
        for patient, score, breached in queue_items:
            velocity = PatientQueue.calculate_vital_velocity_penalty(patient)
            status_text = "BREACH" if breached else ("DECOMPENSATING" if velocity > 0 else "STABLE")
            data.append({
                "Status": status_text,
                "ID": patient.id,
                "HIPAA Token": patient.pseudo_id,
                "Name": patient.name,
                "Age Bracket": patient.vitals.age_category.value.title(),
                "Acuity": f"ESI {patient.effective_esi}" if patient.effective_esi else "Pending",
                "Wait Time": f"{patient.wait_time_minutes} min",
                "Priority Score": score,
                "Vital Velocity (Delta)": f"+{velocity}" if velocity > 0 else "0.0",
                "Chief Complaint": patient.chief_complaint,
                "Pain": f"{patient.vitals.pain_scale}/10",
            })
        return pd.DataFrame(data)

    st.markdown(f"#### Main Emergency Queue ({active_facility.facility_name})")
    if main_q:
        df_main = build_clean_queue_df(main_q)
        st.dataframe(df_main, use_container_width=True, hide_index=True)
    else:
        st.info("Main emergency queue is currently clear.")

    if surge_toggle:
        st.divider()
        st.markdown("#### Fast-Track / Minor Injury Diversion Queue (3x Surge Active)")
        if fast_q:
            df_fast = build_clean_queue_df(fast_q)
            st.dataframe(df_fast, use_container_width=True, hide_index=True)
        else:
            st.info("No low-acuity cases currently diverted to Fast-Track.")

    st.divider()
    with st.expander("Stress Simulation Utilities (Vital Crash Simulator)"):
        col_sim1, col_sim2 = st.columns([3, 1])
        target_id = col_sim1.selectbox("Select Patient to Simulate Sudden Vital Decompensation", [p.id for p in all_patients])
        if col_sim2.button("Trigger Vital Crash", use_container_width=True):
            decomp_patient = st.session_state.queue.simulate_vital_decompensation(target_id)
            if decomp_patient:
                new_res = st.session_state.engine.evaluate(decomp_patient)
                decomp_patient.assigned_esi = new_res.esi_level
                st.session_state.queue.repo.update(decomp_patient)
                st.warning(f"Patient {target_id} ({decomp_patient.pseudo_id}) vital crash applied. Priority score elevated.")
                st.rerun()

# -------------------------------------------------------------
# WORKSTATION 3: FHIR V4 BRIDGE & IMMUTABLE AUDIT LEDGER
# -------------------------------------------------------------
with tab_audit:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("#### HL7 FHIR v4 Payload Ingestion Sandbox")
        st.markdown("Simulate bedside telemetry injection via FHIR v4 Observation bundle:")
        if st.button("Inject Sample Bedside FHIR Bundle", use_container_width=True):
            sample_bundle = {
                "resourceType": "Bundle",
                "id": "BUNDLE-SIM-001",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "PT-FHIR-SIM",
                            "name": [{"given": ["Arthur"], "family": "Pendelton"}],
                            "birthDate": "1954-06-20",
                            "extension": [{"url": "http://hl7.org/fhir/StructureDefinition/patient-medication", "valueString": "Warfarin 5mg daily"}]
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
                            "valueQuantity": {"value": 118}
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                            "valueQuantity": {"value": 85}
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Encounter",
                            "reasonCode": [{"text": "Bedside Telemetry: Acute drop in SBP with tachycardia on Warfarin"}]
                        }
                    }
                ]
            }
            fhir_patient = FHIRAdapter.parse_bundle(sample_bundle)
            fhir_res = st.session_state.engine.evaluate(fhir_patient)
            fhir_patient.assigned_esi = fhir_res.esi_level
            st.session_state.queue.repo.add(fhir_patient)
            risk_doc = FHIRAdapter.export_risk_assessment(fhir_patient, fhir_res)
            st.success(f"FHIR Bundle ingested for {fhir_patient.name} ({fhir_patient.pseudo_id}) -> ESI {fhir_res.esi_level}")
            st.json(risk_doc)

    with col_f2:
        st.markdown("#### Regulatory Audit Trail")
        events = st.session_state.audit_logger.repo.get_events()
        st.markdown(f"**Total Events:** `{len(events)}` | **De-Identification:** `SHA-256 Active`")

    st.divider()
    events = st.session_state.audit_logger.repo.get_events()
    if events:
        for ev in reversed(events):
            token = ev.get("pseudonymized_token", ev.get("patient_id"))
            age_cat = ev.get("demographics", {}).get("age_category", "unknown")
            final_esi = ev.get("clinician_decision", {}).get("final_esi")
            was_ovr = ev.get("clinician_decision", {}).get("was_overridden", False)
            timestamp = ev.get("timestamp", "")
            
            card_title = f"{timestamp} | {token} ({age_cat.title()}) | Final Decision: ESI {final_esi} {'[OVERRIDE COMMIT]' if was_ovr else '[AI ACCEPTED]'}"
            with st.expander(card_title):
                st.json(ev)
    else:
        st.info("No audit events committed in this session. Assess and commit decisions to populate ledger.")