"""
CarePath AI - Streamlit Frontend (Self-Contained, no HTTP backend needed)
All ML/backend logic is imported and called directly.
HCI Design Principles: colorblind-safe palette, no blue for important messages,
icon+color for status (never color alone), complete HTML blocks (no split divs).
"""

import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

# ── Path setup so imports work on Streamlit Cloud ────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Inject secrets into environment so config.py can read them ───────────────
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

# ── Import backend modules directly ──────────────────────────────────────────
_BACKEND_OK = False
_BACKEND_ERR = ""
try:
    from app.backend.db import (
        get_stats,
        get_metric_summary,
        get_upload,
        init_db,
        save_chat,
        save_metric,
        save_reminder,
        save_upload,
    )
    from app.backend.handout import build_patient_handout_pdf
    from app.backend.metrics import citation_coverage, estimate_readability_score, grounded_answer
    from app.ml.advanced_features import (
        build_recovery_scorecard,
        generate_doctor_questions,
        medication_safety_scan,
        simulate_adherence_impact,
    )
    from app.ml.llm import get_llm_provider
    from app.ml.parser import extract_entities, extract_text
    from app.ml.recommender import (
        DISCLAIMER,
        build_care_plan,
        build_red_flags,
        build_reminders,
        generate_patient_summary,
    )
    from app.ml.risk import compute_risk_score
    from app.rag.retriever import retrieve_context

    init_db()
    _BACKEND_OK = True
except Exception as _e:
    _BACKEND_ERR = str(_e)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="CarePath AI", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] { background:#f4f6f8; font-family:'Segoe UI',Arial,sans-serif; color:#212121; }
[data-testid="stSidebar"] { background:linear-gradient(170deg,#263238 0%,#37474f 100%); }
[data-testid="stSidebar"] * { color:#eceff1 !important; }
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-baseweb="base-input"],
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] div[class] { background:#37474f !important; border-color:#546e7a !important; }
[data-testid="stSidebar"] input { background:#37474f !important; color:#eceff1 !important; border-color:#546e7a !important; }
[data-testid="stSidebar"] [data-baseweb="select"] div { background:#37474f !important; color:#eceff1 !important; }
[data-testid="stSidebar"] [data-baseweb="popover"] { background:#37474f !important; }
[data-testid="stSidebar"] [role="listbox"] { background:#37474f !important; }
[data-testid="stSidebar"] [role="option"] { background:#37474f !important; color:#eceff1 !important; }
[data-testid="stSidebar"] [role="option"]:hover { background:#455a64 !important; }
[data-testid="stSidebar"] button { background:#37474f !important; border-color:#546e7a !important; color:#eceff1 !important; }
[data-testid="stSidebar"] svg { fill:#eceff1 !important; }
.card { background:#fff; border-radius:12px; padding:20px 24px; margin-bottom:16px; box-shadow:0 1px 6px rgba(0,0,0,0.09); }
.card-green  { border-left:5px solid #2e7d32; }
.card-amber  { border-left:5px solid #e65100; }
.card-red    { border-left:5px solid #b71c1c; }
.card-teal   { border-left:5px solid #00695c; }
.card-purple { border-left:5px solid #6a1b9a; }
.card-slate  { border-left:5px solid #37474f; }
.sec-hdr { font-size:1rem; font-weight:700; color:#263238; margin:0 0 12px 0; padding-bottom:6px; border-bottom:2px solid #eceff1; }
.urdu-box { direction:rtl; text-align:right; font-family:'Noto Nastaliq Urdu','Traditional Arabic',serif; font-size:1.1rem; line-height:2.2rem; background:#e8f5e9; border-right:5px solid #2e7d32; border-radius:0 10px 10px 0; padding:14px 18px 14px 12px; color:#1b5e20; }
.badge { display:inline-block; padding:4px 16px; border-radius:20px; font-size:0.85rem; font-weight:700; }
.badge-low    { background:#e8f5e9; color:#1b5e20; border:1.5px solid #2e7d32; }
.badge-medium { background:#fff3e0; color:#bf360c; border:1.5px solid #e65100; }
.badge-high   { background:#ffebee; color:#7f0000; border:1.5px solid #b71c1c; }
.bar-wrap { margin:7px 0; }
.bar-lbl  { font-size:0.82rem; color:#455a64; margin-bottom:3px; font-weight:600; }
.bar-bg   { background:#eceff1; border-radius:20px; height:11px; }
.bar-fill { height:11px; border-radius:20px; }
.cp-tbl { width:100%; border-collapse:collapse; font-size:0.88rem; }
.cp-tbl th { background:#263238; color:#fff; padding:9px 12px; text-align:left; font-weight:600; }
.cp-tbl td { padding:8px 12px; border-bottom:1px solid #f0f0f0; color:#212121; }
.cp-tbl tr:nth-child(even) td { background:#f9f9f9; }
.chip { display:inline-block; padding:3px 12px; border-radius:20px; font-size:0.78rem; font-weight:600; margin:3px 3px 3px 0; }
.chip-med  { background:#e0f2f1; color:#004d40; border:1px solid #00695c; }
.chip-diag { background:#fce4ec; color:#880e4f; border:1px solid #c2185b; }
.chip-test { background:#f3e5f5; color:#4a148c; border:1px solid #7b1fa2; }
.chip-fu   { background:#fff8e1; color:#e65100; border:1px solid #f57c00; }
.chip-none { background:#f5f5f5; color:#757575; border:1px solid #bdbdbd; }
.chat-q  { font-size:0.86rem; font-weight:700; color:#263238; margin:12px 0 4px; }
.chat-a  { background:#e8f5e9; border-left:4px solid #2e7d32; border-radius:0 12px 12px 12px; padding:14px 18px; font-size:0.91rem; line-height:1.75; color:#1b5e20; }
.chat-cite { background:#f9f9f9; border-left:3px solid #78909c; padding:7px 12px; font-size:0.77rem; color:#546e7a; margin-top:5px; border-radius:0 8px 8px 0; }
[data-testid="stFileUploaderDropzone"] { border:2px dashed #00695c !important; border-radius:12px !important; background:#e0f2f1 !important; }
.stButton>button[kind="primary"] { background:linear-gradient(135deg,#263238,#37474f) !important; color:#fff !important; border-radius:10px !important; font-weight:700 !important; border:none !important; box-shadow:0 3px 10px rgba(0,0,0,0.25) !important; }
.disc { background:#fff8e1; border:1.5px solid #ffe082; border-radius:8px; padding:10px 16px; font-size:0.82rem; color:#5d4037; margin-top:14px; text-align:center; }
[data-testid="stMetric"] { background:#fff; border-radius:12px; padding:14px 18px; box-shadow:0 1px 5px rgba(0,0,0,0.08); }
[data-testid="stMetricValue"] { color:#263238 !important; font-weight:700 !important; }
[data-baseweb="tab-list"] { gap:8px; }
[data-baseweb="tab"] { font-weight:600 !important; font-size:0.92rem !important; color:#37474f !important; padding:8px 18px !important; }
[aria-selected="true"][data-baseweb="tab"] { color:#00695c !important; border-bottom:3px solid #00695c !important; }
</style>
""", unsafe_allow_html=True)


# ── Helper UI functions ───────────────────────────────────────────────────────
def risk_badge(risk: str) -> str:
    icon = {"low": "✅", "medium": "⚠️", "high": "🚨"}.get(risk.lower(), "❓")
    cls  = {"low": "badge-low", "medium": "badge-medium", "high": "badge-high"}.get(risk.lower(), "badge-low")
    return f'<span class="badge {cls}">{icon} {risk.upper()}</span>'


def bar_html(label: str, value: int, color: str) -> str:
    v = max(0, min(100, value))
    return (f'<div class="bar-wrap"><div class="bar-lbl">{label} — <strong>{v}/100</strong></div>'
            f'<div class="bar-bg"><div class="bar-fill" style="width:{v}%;background:{color};"></div></div></div>')


def chips(items: List[str], cls: str, prefix: str = "") -> str:
    if not items:
        return '<span class="chip chip-none">None detected</span>'
    return "".join(f'<span class="chip {cls}">{prefix}{i}</span>' for i in items)


def med_chips(meds: List[Dict]) -> str:
    if not meds:
        return '<span class="chip chip-none">None detected</span>'
    return "".join(f'<span class="chip chip-med">💊 {m["name"]} {m["dose"]}</span>' for m in meds)


# ── Direct processing functions (no HTTP) ────────────────────────────────────
def process_document_directly(uploaded: Any, age: int, condition: str, language: str) -> Optional[Dict[str, Any]]:
    try:
        content  = uploaded.getvalue()
        filename = uploaded.name
        start    = time.perf_counter()

        extracted_text = extract_text(filename, content)
        if not extracted_text.strip():
            extracted_text = "No meaningful text was detected. Please provide a clearer report."

        entities          = extract_entities(extracted_text)
        summary_en, summary_ur = generate_patient_summary(extracted_text, entities)
        care_plan         = build_care_plan(entities, age=age, condition=condition or None)
        reminders         = build_reminders(entities)
        red_flags         = build_red_flags(entities)
        risk_score, risk_factors = compute_risk_score(entities, age=age)
        safety_alerts     = medication_safety_scan(entities)
        recovery_scorecard = build_recovery_scorecard(entities, age=age, risk_score=risk_score)
        doctor_questions  = generate_doctor_questions(entities, condition or None)
        readability       = estimate_readability_score(summary_en)

        upload_payload: Dict[str, Any] = {
            "filename": filename,
            "file_path": filename,
            "extracted_text": extracted_text,
            "entities": entities,
            "summary_en": summary_en,
            "summary_ur": summary_ur,
            "care_plan": care_plan,
            "reminders": reminders,
            "red_flags": red_flags,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
        }
        upload_id = save_upload(upload_payload)
        for r in reminders:
            save_reminder(upload_id, r["message"], r["remind_at"])

        latency_ms = (time.perf_counter() - start) * 1000
        save_metric("process_latency_ms", latency_ms, f"upload:{upload_id}")
        save_metric("summary_readability_score", readability, f"upload:{upload_id}")

        return {
            "upload_id": upload_id,
            "filename": filename,
            "entities": entities,
            "summary_en": summary_en,
            "summary_ur": summary_ur,
            "care_plan": care_plan,
            "reminders": reminders,
            "red_flags": red_flags,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "safety_alerts": safety_alerts,
            "recovery_scorecard": recovery_scorecard,
            "doctor_questions": doctor_questions,
            "disclaimer": DISCLAIMER,
        }
    except Exception as exc:
        st.error(f"❌ Processing error: {exc}")
        return None


def chat_directly(upload_id: int, question: str) -> Optional[Dict]:
    try:
        upload = get_upload(upload_id)
        context, citations = retrieve_context(question, upload["extracted_text"])
        prompt = (
            "You are CarePath AI. Only answer using provided context.\n"
            "If answer is not found, clearly say so.\n\n"
            f"Question: {question}\n\nContext:\n{context}\n\n"
            f"Disclaimer: {DISCLAIMER}"
        )
        generated = get_llm_provider().generate(prompt)
        answer    = grounded_answer(citations, generated)
        coverage  = citation_coverage(question, citations)
        save_metric("chat_citation_coverage", coverage, f"upload:{upload_id}")
        save_chat(upload_id, question, answer, citations)
        return {"answer": answer, "citations": citations}
    except Exception as exc:
        st.error(f"❌ Chat error: {exc}")
        return None


def export_handout_directly(upload_id: int) -> Optional[bytes]:
    try:
        upload = get_upload(upload_id)
        return build_patient_handout_pdf(upload)
    except Exception as exc:
        st.error(f"❌ PDF export error: {exc}")
        return None


def simulate_directly(upload_id: int, adherence_percent: int) -> Optional[Dict]:
    try:
        upload  = get_upload(upload_id)
        outcome = simulate_adherence_impact(upload["risk_score"], adherence_percent)
        save_metric("adherence_simulation_percent", float(adherence_percent), f"upload:{upload_id}")
        return outcome
    except Exception as exc:
        st.error(f"❌ Simulation error: {exc}")
        return None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:0;margin:0;">
        <div style="font-size:1.3rem;font-weight:700;color:#fff;margin:0 0 2px 0;">🏥 CarePath AI</div>
        <div style="font-size:0.8rem;color:#b0bec5;margin:0 0 12px 0;">Generative AI Care Assistant</div>
        <hr style="border:none;border-top:1px solid #546e7a;margin:0 0 12px 0;">
        <div style="font-size:0.9rem;font-weight:700;color:#eceff1;margin:0 0 8px 0;">👤 Patient Profile</div>
    </div>
    """, unsafe_allow_html=True)
    age = st.number_input("Age", min_value=0, max_value=120, value=40, step=1)
    condition = st.text_input("Known condition (optional)", placeholder="e.g. diabetes")
    language_preference = st.selectbox("Language", ["both", "english", "urdu"])
    st.markdown('<hr style="border:none;border-top:1px solid #546e7a;margin:8px 0;">', unsafe_allow_html=True)
    st.session_state["pitch_mode"] = st.toggle("🎯 Judge pitch mode", value=True)
    st.markdown('<hr style="border:none;border-top:1px solid #546e7a;margin:8px 0;">', unsafe_allow_html=True)
    st.markdown('<div style="background:#37474f;border-radius:8px;padding:10px 12px;font-size:0.82rem;">⚕️ <strong>Not a medical diagnosis.</strong><br>Always consult a licensed doctor.</div>', unsafe_allow_html=True)

# ── Backend error banner ──────────────────────────────────────────────────────
if not _BACKEND_OK:
    st.markdown(
        f'<div class="card card-red"><p class="sec-hdr">⚠️ Backend Module Error</p>'
        f'<p style="font-size:0.85rem;color:#7f0000;">{_BACKEND_ERR}</p></div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#263238,#37474f);border-radius:14px;padding:26px 30px;margin-bottom:20px;color:#eceff1;">
  <h1 style="margin:0;font-size:1.9rem;color:#fff;">🏥 CarePath AI</h1>
  <p style="margin:6px 0 0;font-size:0.95rem;opacity:0.85;">Upload a medical report — receive bilingual summaries, a personalized care plan, medication safety checks, risk scoring, and grounded Q&A.</p>
</div>
""", unsafe_allow_html=True)

tab_care, tab_admin, tab_pitch = st.tabs(["🩺 Care Assistant", "📊 Admin Insights", "🏆 Pitch Highlights"])

with tab_care:
    st.markdown('<div class="card card-teal"><p class="sec-hdr">📁 Upload Medical Report</p><p style="font-size:0.85rem;color:#004d40;margin:0;">Supported formats: PDF &nbsp;·&nbsp; PNG &nbsp;·&nbsp; JPG &nbsp;·&nbsp; TXT</p></div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload", type=["pdf","png","jpg","jpeg","txt"], label_visibility="collapsed")
    col_btn, col_hint = st.columns([1, 3])
    with col_btn:
        generate_clicked = st.button("⚡ Generate CarePath", type="primary", disabled=uploaded_file is None, use_container_width=True)
    with col_hint:
        if uploaded_file:
            st.markdown(f'<p style="color:#1b5e20;font-weight:700;margin:8px 0;">✅ Ready: {uploaded_file.name}</p>', unsafe_allow_html=True)

    if generate_clicked and uploaded_file:
        with st.spinner("🔍 Extracting clinical data and generating care plan…"):
            result = process_document_directly(uploaded_file, int(age), condition, language_preference)
        if result:
            result["generated_at"] = datetime.utcnow().isoformat()
            st.session_state["last_result"] = result
            st.session_state.pop("chat_history", None)
            st.toast("✅ CarePath generated!", icon="🎉")

    if "last_result" not in st.session_state:
        st.markdown('<div style="text-align:center;padding:56px 20px;color:#78909c;"><div style="font-size:3rem;">📋</div><h3 style="color:#546e7a;">Upload a report above to get started</h3><p>CarePath AI will extract clinical entities, generate a bilingual summary, build a daily care plan, and assess your adherence risk.</p></div>', unsafe_allow_html=True)
        st.stop()

    result = st.session_state["last_result"]
    risk   = result["risk_score"].lower()

    if st.session_state.get("pitch_mode"):
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🎯 Risk Tier",       result["risk_score"].upper())
        k2.metric("💊 Medicines Found", len(result["entities"].get("medicines", [])))
        k3.metric("📅 Follow-ups",      len(result["entities"].get("follow_up", [])))
        k4.metric("🆔 Upload ID",       result["upload_id"])
        st.markdown("<br>", unsafe_allow_html=True)

    col_dl, _ = st.columns([1, 4])
    with col_dl:
        if st.button("📥 Download Patient Handout PDF", type="primary", use_container_width=True):
            with st.spinner("Building PDF…"):
                pdf_bytes = export_handout_directly(result["upload_id"])
            if pdf_bytes:
                st.download_button(
                    "💾 Save Handout PDF",
                    data=pdf_bytes,
                    file_name=f"carepath_handout_{result['upload_id']}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )

    st.markdown("---")

    col_en, col_ur = st.columns(2)
    with col_en:
        st.markdown(f'<div class="card card-teal"><p class="sec-hdr">📋 Patient Summary (English)</p><p style="font-size:0.93rem;line-height:1.75;color:#1b5e20;">{result["summary_en"]}</p></div>', unsafe_allow_html=True)
    with col_ur:
        ur_clean = result["summary_ur"].split("English summary excerpt:")[0].replace("اردو خلاصہ (خودکار):", "").strip()
        st.markdown(f'<div class="card card-green"><p class="sec-hdr">📋 خلاصہ (اردو)</p><div class="urdu-box">{ur_clean}</div></div>', unsafe_allow_html=True)

    col_plan, col_score = st.columns([3, 2])
    with col_plan:
        plan_rows = "".join(f"<tr><td>⏰ <strong>{r['time']}</strong></td><td>{r['activity']}</td></tr>" for r in result["care_plan"])
        st.markdown(f'<div class="card card-slate"><p class="sec-hdr">📅 Personalized Daily Care Plan</p><table class="cp-tbl"><thead><tr><th>Time</th><th>Activity</th></tr></thead><tbody>{plan_rows}</tbody></table></div>', unsafe_allow_html=True)
    with col_score:
        sc   = result["recovery_scorecard"]
        bars = (bar_html("Overall Recovery",     sc["overall_recovery_readiness"], "#00695c") +
                bar_html("Adherence Readiness",  sc["adherence_readiness"],        "#2e7d32") +
                bar_html("Follow-up Clarity",    sc["followup_clarity"],           "#e65100") +
                bar_html("Monitoring Strength",  sc["monitoring_strength"],        "#6a1b9a"))
        st.markdown(f'<div class="card card-purple"><p class="sec-hdr">📈 Recovery Scorecard</p>{bars}</div>', unsafe_allow_html=True)

    col_risk, col_flags, col_safety = st.columns(3)
    with col_risk:
        factors_li = "".join(f"<li style='margin:5px 0;'>{f}</li>" for f in result["risk_factors"])
        card_color = {"low": "card-green", "medium": "card-amber", "high": "card-red"}.get(risk, "card-slate")
        st.markdown(f'<div class="card {card_color}"><p class="sec-hdr">⚡ Adherence Risk</p>{risk_badge(risk)}<p style="font-size:0.82rem;font-weight:700;color:#455a64;margin:12px 0 4px;">Factors:</p><ul style="margin:0;padding-left:18px;font-size:0.84rem;color:#37474f;">{factors_li}</ul></div>', unsafe_allow_html=True)
    with col_flags:
        flags_li = "".join(f"<li style='margin:6px 0;color:#7f0000;'>⚠️ {f}</li>" for f in result["red_flags"])
        st.markdown(f'<div class="card card-red"><p class="sec-hdr">🚨 Red-Flag Warnings</p><ul style="margin:0;padding-left:18px;font-size:0.84rem;">{flags_li}</ul></div>', unsafe_allow_html=True)
    with col_safety:
        alerts = result.get("safety_alerts", [])
        body   = "".join(f"<li style='margin:6px 0;'>⚠️ {a}</li>" for a in alerts) if alerts else '<li style="color:#1b5e20;">✅ No conflicts detected.</li>'
        st.markdown(f'<div class="card card-amber"><p class="sec-hdr">💊 Medication Safety</p><ul style="margin:0;padding-left:18px;font-size:0.84rem;color:#bf360c;">{body}</ul></div>', unsafe_allow_html=True)

    col_rem, col_ent = st.columns(2)
    with col_rem:
        rem_li = "".join(
            f'<li style="margin:8px 0;">🔔 <strong>{r["message"]}</strong><br>'
            f'<span style="font-size:0.77rem;color:#78909c;">{r["remind_at"][:16].replace("T"," ")} UTC</span></li>'
            for r in result["reminders"]
        )
        st.markdown(f'<div class="card card-slate"><p class="sec-hdr">⏰ Reminders</p><ul style="margin:0;padding-left:18px;font-size:0.88rem;">{rem_li}</ul></div>', unsafe_allow_html=True)
    with col_ent:
        ents = result["entities"]
        st.markdown(
            f'<div class="card card-teal"><p class="sec-hdr">🔬 Extracted Clinical Entities</p>'
            f'<p style="font-size:0.8rem;font-weight:700;color:#37474f;margin:6px 0 3px;">Medicines</p>{med_chips(ents.get("medicines",[]))}'
            f'<p style="font-size:0.8rem;font-weight:700;color:#37474f;margin:10px 0 3px;">Diagnoses</p>{chips(ents.get("diagnoses",[]),"chip-diag","🩺 ")}'
            f'<p style="font-size:0.8rem;font-weight:700;color:#37474f;margin:10px 0 3px;">Tests</p>{chips(ents.get("tests",[]),"chip-test","🧪 ")}'
            f'<p style="font-size:0.8rem;font-weight:700;color:#37474f;margin:10px 0 3px;">Follow-up</p>{chips(ents.get("follow_up",[]),"chip-fu","📅 ")}'
            f'</div>', unsafe_allow_html=True)

    dqs = result.get("doctor_questions", [])
    if dqs:
        dq_li = "".join(f'<li style="margin:8px 0;">❓ {q}</li>' for q in dqs)
        st.markdown(f'<div class="card card-purple"><p class="sec-hdr">🩺 Questions to Ask Your Doctor</p><ul style="margin:0;padding-left:18px;font-size:0.88rem;color:#4a148c;">{dq_li}</ul></div>', unsafe_allow_html=True)

    st.markdown('<div class="card card-teal"><p class="sec-hdr">🎮 Adherence Impact Simulator</p><p style="font-size:0.87rem;color:#004d40;margin:0;">Adjust your expected adherence to see projected outcomes and AI coaching tips.</p></div>', unsafe_allow_html=True)
    adherence_val = st.slider("Expected adherence over next 14 days", min_value=40, max_value=100, value=80, step=5, format="%d%%")
    if st.button("🚀 Simulate Outcome", key="sim_btn"):
        with st.spinner("Running simulation…"):
            sim = simulate_directly(result["upload_id"], adherence_val)
        if sim:
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Projected Risk", sim["projected_risk"].upper())
            with sc2:
                ben_li = "".join(f"<li>{b}</li>" for b in sim["expected_benefits"])
                st.markdown(f'<strong style="font-size:0.85rem;color:#1b5e20;">✅ Expected Benefits</strong><ul style="font-size:0.84rem;margin:5px 0;padding-left:16px;color:#37474f;">{ben_li}</ul>', unsafe_allow_html=True)
            with sc3:
                tip_li = "".join(f"<li>{t}</li>" for t in sim["coaching_tips"])
                st.markdown(f'<strong style="font-size:0.85rem;color:#4a148c;">💡 AI Coaching Tips</strong><ul style="font-size:0.84rem;margin:5px 0;padding-left:16px;color:#37474f;">{tip_li}</ul>', unsafe_allow_html=True)

    st.markdown('<div class="card card-green"><p class="sec-hdr">💬 Grounded Q&A Chatbot</p><p style="font-size:0.85rem;color:#1b5e20;margin:0;">Answers grounded in your uploaded report and approved medical knowledge base. Citations shown for every response.</p></div>', unsafe_allow_html=True)
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    for entry in st.session_state["chat_history"]:
        st.markdown(f'<div class="chat-q">🧑 {entry["q"]}</div><div class="chat-a">{entry["a"]}</div>', unsafe_allow_html=True)
        for c in entry.get("citations", []):
            st.markdown(f'<div class="chat-cite">📎 {c}</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    question = st.text_input("Your question", placeholder="e.g. What are my follow-up instructions?", label_visibility="collapsed", key="chat_input")
    col_ask, col_clr = st.columns([1, 6])
    with col_ask:
        ask_clicked = st.button("Ask ➤", disabled=not bool(question.strip()), use_container_width=True)
    with col_clr:
        if st.button("🗑️ Clear chat", key="clear_chat"):
            st.session_state["chat_history"] = []
            st.rerun()
    if ask_clicked and question.strip():
        with st.spinner("Searching report + knowledge base…"):
            cd = chat_directly(result["upload_id"], question)
        if cd:
            st.session_state["chat_history"].append({"q": question, "a": cd["answer"], "citations": cd.get("citations", [])})
            st.rerun()

    st.markdown(f'<div class="disc">⚕️ {result["disclaimer"]}</div>', unsafe_allow_html=True)

with tab_admin:
    st.markdown('<div class="card card-teal"><p class="sec-hdr">📊 Admin Analytics Dashboard</p></div>', unsafe_allow_html=True)
    try:
        uploads, chats, reminders_count = get_stats()
        c1, c2, c3 = st.columns(3)
        c1.metric("📁 Total Uploads", uploads)
        c2.metric("💬 Total Chats", chats)
        c3.metric("🔔 Total Reminders", reminders_count)
        avg_metrics = get_metric_summary()
        if avg_metrics:
            metric_bars = "".join(bar_html(k.replace("_"," ").title(), int(min(v, 100)), "#00695c") for k, v in avg_metrics.items())
            st.markdown(f'<div class="card card-teal"><p class="sec-hdr">⚙️ Average Evaluation Metrics</p>{metric_bars}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="card card-slate"><p style="color:#546e7a;font-size:0.88rem;">No metrics yet — upload a report and use the chatbot to populate.</p></div>', unsafe_allow_html=True)
    except Exception as exc:
        st.markdown(f'<div class="card card-amber"><p style="color:#bf360c;">Admin panel error: {exc}</p></div>', unsafe_allow_html=True)

with tab_pitch:
    st.markdown('<div style="background:linear-gradient(135deg,#263238,#37474f);border-radius:14px;padding:26px 30px;margin-bottom:20px;color:#eceff1;"><h2 style="margin:0;color:#fff;">🏆 Why CarePath AI Wins</h2><p style="opacity:0.8;margin:6px 0 0;">Judge-friendly pitch highlights</p></div>', unsafe_allow_html=True)
    pitch_items = [
        ("🤖 Generative AI Innovation", "card-teal", "#00695c", "Bilingual clinical simplification (English + Urdu) via Groq Llama 3.1. Source-grounded Q&A with citation snippets eliminates hallucinations."),
        ("🌍 Real-world Impact", "card-green", "#1b5e20", "70% of medication non-adherence stems from patient confusion. CarePath AI provides culturally appropriate Urdu output and structured daily care plans for low-literacy populations in Pakistan and South Asia."),
        ("⚙️ Technical Implementation", "card-purple", "#4a148c", "End-to-end pipeline: OCR → entity extraction → LLM summary → RAG chatbot → risk scoring → adherence simulation → PDF export. FastAPI · Streamlit · Docker · APScheduler · SQLite."),
        ("📋 Reproducibility", "card-slate", "#263238", "10-minute local setup, Docker Compose, pytest suite, sample data reports, seed script, architecture diagram, and HACKATHON_SUBMISSION.md."),
    ]
    p1, p2 = st.columns(2)
    for col, (title, card_cls, color, desc) in zip([p1, p2, p1, p2], pitch_items):
        with col:
            st.markdown(f'<div class="card {card_cls}"><p class="sec-hdr" style="color:{color};">{title}</p><p style="font-size:0.88rem;color:#37474f;line-height:1.7;">{desc}</p></div>', unsafe_allow_html=True)
