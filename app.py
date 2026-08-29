"""
PatientTriage.ai — Clinical Streamlit Decision Support HUD.
Features:
- Workstation 1: Real-time Intake & Algorithmic Triage Engine with Active VOI
- Workstation 2: Dynamic Waiting Room Radar with Deterioration Tracking & 3x Surge Fast-Track
- Workstation 3: Immutable Regulatory Audit Stream & Clinician Override Manager
"""

import streamlit as st
import pandas as pd
from triage.models import PatientRecord, Vitals
from triage.engine import AlgorithmicTriageEngine
from triage.queue import PatientQueue
from triage.audit import AuditLogger
from triage.cohort import load_benchmark_cohort

# Streamlit Page Config
st.set_page_config(
    page_title="PatientTriage.ai | Clinical HUD",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State Singletons
if "engine" not in st.session_state:
    st.session_state.engine = AlgorithmicTriageEngine()
if "queue" not in st.session_state:
    queue = PatientQueue()
    for p in load_benchmark_cohort():
        # Pre-assign baseline ESI
        res = st.session_state.engine.evaluate(p)
        p.assigned_esi = res.esi_level
        queue.repo.add(p)
    st.session_state.queue = queue
if "audit_logger" not in st.session_state:
    st.session_state.audit_logger = AuditLogger()
if "clinician_id" not in st.session_state:
    st.session_state.clinician_id = "RN-4402"

# Sidebar Telemetry & Controls
st.sidebar.title("🏥 PatientTriage.ai")
st.sidebar.markdown(f"**Triaging Clinician:** `{st.session_state.clinician_id}`")
st.sidebar.markdown("**Decision Core:** `Algorithmic Baseline (<1ms)`")

st.sidebar.divider()
st.sidebar.subheader("🚨 Emergency Dept Controls")
surge_toggle = st.sidebar.toggle("⚡ 3× Surge Mode", value=st.session_state.queue.surge_mode)
st.session_state.queue.surge_mode = surge_toggle

if st.sidebar.button("⏱️ Advance Wait (+15 min)"):
    st.session_state.queue.simulate_time_advance(15)
    st.rerun()

if st.sidebar.button("🔄 Reset to Initial Benchmark"):
    st.session_state.queue.repo.clear()
    for p in load_benchmark_cohort():
        res = st.session_state.engine.evaluate(p)
        p.assigned_esi = res.esi_level
        st.session_state.queue.repo.add(p)
    st.rerun()

# Global Header Status Bar
all_patients = st.session_state.queue.repo.get_all()
breached_count = sum(1 for p in all_patients if st.session_state.queue.is_breach(p))
occupancy_str = "96% (CRITICAL)" if surge_toggle else "78% (NOMINAL)"

col_h1, col_h2, col_h3, col_h4 = st.columns(4)
col_h1.metric("ED Status", "SURGE ACTIVE" if surge_toggle else "ONLINE", delta="Surge 3×" if surge_toggle else "Nominal")
col_h2.metric("Occupancy Rate", occupancy_str)
col_h3.metric("Patients Waiting", len(all_patients))
col_h4.metric("Re-Triage Breaches", breached_count, delta_color="inverse")

st.divider()

# Tab Workstations
tab_intake, tab_radar, tab_audit = st.tabs([
    "📥 Intake & Clinical Scorer",
    "📡 Waiting Room Deterioration Radar",
    "📜 Immutable Audit & Override Log",
])

# -------------------------------------------------------------
# TAB 1: INTAKE & SCORER
# -------------------------------------------------------------
with tab_intake:
    st.subheader("Patient Clinical Assessment & VOI Assistant")

    # Preset Quick Selectors
    col_preset1, col_preset2, col_preset3 = st.columns(3)
    patient_names = [f"{p.id}: {p.name} ({p.vitals.age_category.value})" for p in all_patients]
    selected_idx = col_preset1.selectbox("Select Patient to Assess / Edit", range(len(patient_names)), format_func=lambda i: patient_names[i])
    current_patient = all_patients[selected_idx]

    with st.expander("📝 Edit Patient Parameters & Vitals", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        v_hr = c1.number_input("Heart Rate (bpm)", 20, 260, current_patient.vitals.heart_rate)
        v_sbp = c2.number_input("Systolic BP (mmHg)", 30, 260, current_patient.vitals.systolic_bp)
        v_dbp = c3.number_input("Diastolic BP (mmHg)", 20, 160, current_patient.vitals.diastolic_bp)
        v_rr = c4.number_input("Resp Rate (bpm)", 6, 80, current_patient.vitals.resp_rate)

        c5, c6, c7, c8 = st.columns(4)
        v_spo2 = c5.number_input("SpO2 (%)", 50.0, 100.0, float(current_patient.vitals.spo2), step=1.0)
        v_temp = c6.number_input("Temp (°C)", 28.0, 43.0, float(current_patient.vitals.temp_celsius), step=0.1)
        v_pain = c7.slider("Pain Scale (0-10)", 0, 10, current_patient.vitals.pain_scale)
        v_age = c8.number_input("Age (Years)", 0.1, 120.0, float(current_patient.vitals.age), step=0.1)

        v_complaint = st.text_input("Chief Complaint", current_patient.chief_complaint)
        v_history_str = st.text_input("Past Medical History (comma-separated)", ", ".join(current_patient.history))

        if st.button("💾 Update Patient Intake"):
            current_patient.vitals = Vitals(
                age=v_age, heart_rate=v_hr, systolic_bp=v_sbp, diastolic_bp=v_dbp,
                resp_rate=v_rr, spo2=v_spo2, temp_celsius=v_temp, pain_scale=v_pain,
            )
            current_patient.chief_complaint = v_complaint
            current_patient.history = [h.strip() for h in v_history_str.split(",") if h.strip()]
            st.session_state.queue.repo.update(current_patient)
            st.success("Patient updated.")
            st.rerun()

    # Evaluate Patient
    result = st.session_state.engine.evaluate(current_patient)
    current_patient.assigned_esi = result.esi_level
    st.session_state.queue.repo.update(current_patient)

    # Display AI Assessment Card
    col_card1, col_card2 = st.columns([1, 2])

    with col_card1:
        st.markdown("### AI Triage Recommendation")
        esi_colors = {1: "#D32F2F", 2: "#F57C00", 3: "#FBC02D", 4: "#388E3C", 5: "#1976D2"}
        st.markdown(
            f"""
            <div style="background-color:{esi_colors.get(result.esi_level, '#333')}; padding:18px; border-radius:10px; color:white; text-align:center;">
                <h1 style="margin:0; font-size:42px;">ESI Level {result.esi_level}</h1>
                <p style="margin:5px 0 0 0; font-size:18px;"><b>Confidence: {int(result.confidence * 100)}%</b></p>
                <p style="margin:0; font-size:13px;">{"⚠️ Deterministic Red-Line Triggered" if result.deterministic_rule_hit else "Algorithmic Risk Scorer"}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Clinician Override")
        new_override = st.selectbox("Assign Manual ESI", [None, 1, 2, 3, 4, 5], index=0 if current_patient.override_esi is None else current_patient.override_esi)
        override_justification = st.text_input("Override Reason (Mandatory if changing)", value=current_patient.override_reason or "")

        if st.button("🔒 Commit Clinician Decision"):
            if new_override is not None and new_override != result.esi_level and not override_justification.strip():
                st.error("Mandatory regulatory requirement: Justification text required for override.")
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
                st.success("Decision committed to immutable audit log.")
                st.rerun()

    with col_card2:
        st.markdown("### Clinical Reasoning & Findings")
        for exp in result.explanation:
            st.markdown(f"- {exp}")

        if result.is_ambiguous and result.recommended_followups:
            st.warning("⚠️ **Active VOI Assistant (Diagnostic Entropy Detected)**")
            for q in result.recommended_followups:
                st.markdown(f"**Targeted Query:** *{q}*")
                ans = st.text_input(f"Clinician Check / Patient Response:", value=current_patient.answers_to_followups.get(q, ""), key=f"voi_{q}")
                if st.button(f"Submit Follow-Up Response", key=f"btn_{q}"):
                    current_patient.answers_to_followups[q] = ans
                    st.session_state.queue.repo.update(current_patient)
                    st.rerun()

# -------------------------------------------------------------
# TAB 2: WAITING ROOM RADAR
# -------------------------------------------------------------
with tab_radar:
    st.subheader("Dynamic Queue Deterioration Radar")

    main_q, fast_q = st.session_state.queue.get_ranked_queues()

    def format_queue_df(queue_items):
        records = []
        for patient, score, breached in queue_items:
            records.append({
                "Status": "🚨 RE-TRIAGE BREACH" if breached else "🟢 Safe",
                "Patient ID": patient.id,
                "Name": patient.name,
                "Age Bracket": patient.vitals.age_category.value.title(),
                "Effective ESI": f"ESI {patient.effective_esi}" if patient.effective_esi else "Unassigned",
                "Wait Time": f"{patient.wait_time_minutes} min",
                "Priority Score": score,
                "Complaint": patient.chief_complaint,
                "Pain": f"{patient.vitals.pain_scale}/10",
            })
        return pd.DataFrame(records)

    st.markdown("#### Main Emergency Department Queue")
    if main_q:
        df_main = format_queue_df(main_q)
        st.dataframe(df_main, use_container_width=True)
    else:
        st.info("No patients in main queue.")

    if surge_toggle:
        st.divider()
        st.markdown("#### ⚡ Fast-Track / Minor Injury Diversion Queue (Surge Mode Active)")
        if fast_q:
            df_fast = format_queue_df(fast_q)
            st.dataframe(df_fast, use_container_width=True)
        else:
            st.info("No stable patients currently in Fast-Track diversion.")

    st.divider()
    st.markdown("#### 💥 Deterioration Stress Simulator")
    sim_col1, sim_col2 = st.columns([2, 1])
    target_id = sim_col1.selectbox("Select Patient to Simulate Sudden Vitals Crash", [p.id for p in all_patients])
    if sim_col2.button("📉 Trigger Acute Decompensation"):
        decomp_patient = st.session_state.queue.simulate_vital_decompensation(target_id)
        if decomp_patient:
            new_res = st.session_state.engine.evaluate(decomp_patient)
            decomp_patient.assigned_esi = new_res.esi_level
            st.session_state.queue.repo.update(decomp_patient)
            st.warning(f"Patient {target_id} vitals crashed! Priority score elevated.")
            st.rerun()

# -------------------------------------------------------------
# TAB 3: AUDIT & OVERRIDE LOG
# -------------------------------------------------------------
with tab_audit:
    st.subheader("Immutable Regulatory Event Ledger")
    events = st.session_state.audit_logger.repo.get_events()

    if events:
        st.markdown(f"**Total Audited Actions:** `{len(events)}`")
        for ev in reversed(events):
            with st.expander(f"🕒 {ev['timestamp']} — {ev['patient_id']} ({ev['patient_name']}) — Final ESI: {ev['clinician_decision']['final_esi']}"):
                st.json(ev)
    else:
        st.info("No audit events committed yet in this session. Commit an assessment or override to record ledger entries.")