"""
PatientTriage.ai — Clinical Decision Support HUD (v1 Hardened).
A clean, visual-first dashboard designed for rapid clinical triage assessment,
dynamic deterioration radar monitoring, and immutable regulatory compliance logging.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from triage.models import PatientRecord, Vitals
from triage.engine import AlgorithmicTriageEngine
from triage.queue import PatientQueue
from triage.audit import AuditLogger
from triage.cohort import load_benchmark_cohort

# Page Configuration
st.set_page_config(
    page_title="PatientTriage.ai | Clinical HUD",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Dashboard Styling
st.markdown("""
<style>
    /* Metric Cards & Layout */
    .stMetric {
        background-color: rgba(255, 255, 255, 0.04);
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Clinical Badges */
    .badge-esi-1 { background-color: #B71C1C; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 13px; }
    .badge-esi-2 { background-color: #E65100; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 13px; }
    .badge-esi-3 { background-color: #F57F17; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 13px; }
    .badge-esi-4 { background-color: #2E7D32; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 13px; }
    .badge-esi-5 { background-color: #1565C0; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 13px; }
    
    .status-breach { background-color: #7F1D1D; color: #FCA5A5; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .status-velocity { background-color: #78350F; color: #FCD34D; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .status-stable { background-color: #064E3B; color: #6EE7B7; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    
    .vital-box {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        padding: 10px;
        text-align: center;
    }
    .vital-label { font-size: 11px; color: #94A3B8; text-transform: uppercase; font-weight: 600; }
    .vital-val { font-size: 20px; font-weight: 700; margin-top: 2px; }
    
    /* Clean Divider */
    hr { margin: 16px 0; border: 0; border-top: 1px solid rgba(255, 255, 255, 0.1); }
</style>
""", unsafe_allow_html=True)

# Session State Singletons
if "engine" not in st.session_state:
    st.session_state.engine = AlgorithmicTriageEngine()
if "queue" not in st.session_state:
    queue = PatientQueue()
    for p in load_benchmark_cohort():
        res = st.session_state.engine.evaluate(p)
        p.assigned_esi = res.esi_level
        queue.repo.add(p)
    st.session_state.queue = queue
if "audit_logger" not in st.session_state:
    st.session_state.audit_logger = AuditLogger()
if "clinician_id" not in st.session_state:
    st.session_state.clinician_id = "RN-4402"

# Sidebar Telemetry & System Actions
st.sidebar.markdown("### System Telemetry")
st.sidebar.text(f"Clinician ID: {st.session_state.clinician_id}")
st.sidebar.text("Engine Core: Algorithmic v1 (<1ms)")
st.sidebar.text("Privacy Standard: HIPAA SHA-256")

st.sidebar.divider()
st.sidebar.markdown("### Department Controls")
surge_toggle = st.sidebar.toggle("3x Surge Mode", value=st.session_state.queue.surge_mode)
st.session_state.queue.surge_mode = surge_toggle

col_sb1, col_sb2 = st.sidebar.columns(2)
if col_sb1.button("Advance Wait +15m", use_container_width=True):
    st.session_state.queue.simulate_time_advance(15)
    st.rerun()

if col_sb2.button("Reset Benchmark", use_container_width=True):
    st.session_state.queue.repo.clear()
    for p in load_benchmark_cohort():
        res = st.session_state.engine.evaluate(p)
        p.assigned_esi = res.esi_level
        st.session_state.queue.repo.add(p)
    st.rerun()

# Global Header Status Bar
all_patients = st.session_state.queue.repo.get_all()
breached_count = sum(1 for p in all_patients if st.session_state.queue.is_breach(p))
decompensating_count = sum(1 for p in all_patients if PatientQueue.calculate_vital_velocity_penalty(p) > 0)
occupancy_str = "96% [CRITICAL]" if surge_toggle else "78% [NOMINAL]"

col_h1, col_h2, col_h3, col_h4 = st.columns(4)
col_h1.metric("Department Status", "SURGE ACTIVE" if surge_toggle else "NOMINAL", delta="3x Capacity Load" if surge_toggle else "Nominal Flow")
col_h2.metric("Occupancy Capacity", occupancy_str)
col_h3.metric("Patients in Waiting Queue", len(all_patients), delta=f"{decompensating_count} Deteriorating" if decompensating_count else None, delta_color="inverse")
col_h4.metric("Re-Triage Window Breaches", breached_count, delta="Immediate Action Required" if breached_count else "Within Safe Windows", delta_color="inverse")

st.divider()

# Tab Workstations
tab_intake, tab_radar, tab_audit = st.tabs([
    "Intake & Clinical Decision Scorer",
    "Waiting Room Deterioration Radar",
    "Immutable Audit & Override Ledger",
])

# -------------------------------------------------------------
# WORKSTATION 1: INTAKE & CLINICAL DECISION SCORER
# -------------------------------------------------------------
with tab_intake:
    col_sel1, col_sel2 = st.columns([3, 1])
    patient_names = [f"{p.id} | {p.pseudo_id} -- {p.name} ({p.vitals.age_category.value.title()}, {p.vitals.age:.1f}y)" for p in all_patients]
    selected_idx = col_sel1.selectbox("Select Patient from Intake / Waiting Fleet", range(len(patient_names)), format_func=lambda i: patient_names[i])
    current_patient = all_patients[selected_idx]

    col_sel2.markdown(f"""
    <div style="background-color:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1); border-radius:6px; padding:10px 14px;">
        <span style="font-size:11px; color:#94A3B8; text-transform:uppercase; font-weight:600;">HIPAA Token</span><br>
        <span style="font-size:16px; font-weight:700; font-family:monospace;">{current_patient.pseudo_id}</span>
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

    # Vitals Strip
    v = current_patient.vitals
    v_cols = st.columns(6)
    v_cols[0].markdown(f"""<div class="vital-box"><div class="vital-label">Heart Rate</div><div class="vital-val">{v.heart_rate} <span style="font-size:12px; font-weight:400;">bpm</span></div></div>""", unsafe_allow_html=True)
    v_cols[1].markdown(f"""<div class="vital-box"><div class="vital-label">Blood Pressure</div><div class="vital-val">{v.systolic_bp}/{v.diastolic_bp}</div></div>""", unsafe_allow_html=True)
    v_cols[2].markdown(f"""<div class="vital-box"><div class="vital-label">Resp Rate</div><div class="vital-val">{v.resp_rate} <span style="font-size:12px; font-weight:400;">/min</span></div></div>""", unsafe_allow_html=True)
    v_cols[3].markdown(f"""<div class="vital-box"><div class="vital-label">SpO2</div><div class="vital-val">{v.spo2:.0f}%</div></div>""", unsafe_allow_html=True)
    v_cols[4].markdown(f"""<div class="vital-box"><div class="vital-label">Core Temp</div><div class="vital-val">{v.temp_celsius:.1f}°C</div></div>""", unsafe_allow_html=True)
    v_cols[5].markdown(f"""<div class="vital-box"><div class="vital-label">Pain Score</div><div class="vital-val">{v.pain_scale}/10</div></div>""", unsafe_allow_html=True)

    # Evaluate Patient
    result = st.session_state.engine.evaluate(current_patient)
    current_patient.assigned_esi = result.esi_level
    st.session_state.queue.repo.update(current_patient)

    st.markdown("<br>", unsafe_allow_html=True)

    # Primary Decision Presentation
    col_dec1, col_dec2 = st.columns([1, 2])

    with col_dec1:
        esi_color_map = {
            1: ("#B71C1C", "Resuscitation (Immediate Life Threat)"),
            2: ("#E65100", "Emergent (High Risk / Physiological Danger)"),
            3: ("#F57F17", "Urgent (Stable Vitals / 2+ Resources)"),
            4: ("#2E7D32", "Less Urgent (Stable Vitals / 1 Resource)"),
            5: ("#1565C0", "Non-Urgent (Routine Exam / 0 Resources)"),
        }
        bg_col, esi_title = esi_color_map.get(result.esi_level, ("#333", "Acuity Level"))

        st.markdown(f"""
        <div style="background-color:{bg_col}; padding:20px; border-radius:8px; color:white; text-align:center; box-shadow:0 4px 6px -1px rgba(0,0,0,0.3);">
            <div style="font-size:13px; text-transform:uppercase; letter-spacing:1px; font-weight:600; opacity:0.9;">Triage Recommendation</div>
            <div style="font-size:46px; font-weight:800; line-height:1.1; margin:8px 0;">ESI LEVEL {result.esi_level}</div>
            <div style="font-size:13px; font-weight:600; opacity:0.95;">{esi_title}</div>
            <div style="margin-top:14px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.2); font-size:14px;">
                Confidence: <strong>{int(result.confidence * 100)}%</strong> ({'High' if result.confidence >= 0.85 else 'Calibrated Medium' if result.confidence >= 0.70 else 'Uncertain / Escallated'})
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
        
        # Clinical Finding Items
        for item in result.explanation:
            st.markdown(f"-- {item}")

        # Active Value of Information (VOI) Assistant
        if result.is_ambiguous and result.recommended_followups:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <div style="background-color:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); border-radius:6px; padding:12px;">
                <div style="color:#FBBF24; font-weight:700; font-size:13px; text-transform:uppercase; margin-bottom:4px;">Active Value-of-Information (VOI) Query</div>
                <div style="font-size:12px; color:#D1D5DB; margin-bottom:8px;">Epistemic diagnostic entropy detected. Targeted clinical query triggered to collapse uncertainty:</div>
            </div>
            """, unsafe_allow_html=True)

            for q in result.recommended_followups:
                st.markdown(f"**Targeted Question:** `{q}`")
                ans_col1, ans_col2 = st.columns([3, 1])
                ans_text = ans_col1.text_input("Enter Response or Clinical Observation:", value=current_patient.answers_to_followups.get(q, ""), key=f"q_{q}")
                if ans_col2.button("Submit Answer", key=f"btn_{q}", use_container_width=True):
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

    st.markdown("#### Main Emergency Queue (Ranked by Deterioration Score)")
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
# WORKSTATION 3: IMMUTABLE AUDIT & OVERRIDE LEDGER
# -------------------------------------------------------------
with tab_audit:
    events = st.session_state.audit_logger.repo.get_events()
    
    col_aud1, col_aud2 = st.columns([3, 1])
    col_aud1.markdown("#### Regulatory Audit Trail")
    col_aud2.markdown(f"**Total Events:** `{len(events)}` | **De-Identification:** `SHA-256 Active`")

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