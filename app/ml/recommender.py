from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from app.ml.llm import get_llm_provider


DISCLAIMER = "Not a medical diagnosis; consult licensed doctor."


def generate_patient_summary(text: str, entities: Dict[str, Any]) -> Tuple[str, str]:
    llm = get_llm_provider()
    meds = ", ".join(m["name"] for m in entities.get("medicines", [])) or "medications not clearly detected"
    fallback_summary = _deterministic_summary(text, entities)
    prompt = (
        "You are CarePath AI writing for a patient.\n"
        "Write 4-6 short sentences in plain English.\n"
        "Do NOT ask questions. Do NOT say the report is unclear. Do NOT mention being an AI.\n"
        "Include: key condition/findings, medicines if available, follow-up, and immediate safety note.\n"
        "If medicine or follow-up is missing, explicitly say patient should confirm with doctor.\n\n"
        f"Detected medicines: {meds}\n"
        f"Detected follow-up: {entities.get('follow_up', [])}\n"
        f"Detected diagnoses: {entities.get('diagnoses', [])}\n"
        f"Text excerpt:\n{text[:1500]}"
    )
    try:
        model_summary = llm.generate(prompt).strip()
    except Exception:
        model_summary = ""
    summary_en = _sanitize_summary(model_summary, fallback_summary)
    summary_ur = _translate_stub_to_urdu(summary_en, entities)
    return summary_en, summary_ur


def _med_times(frequency: str) -> List[str]:
    """Map frequency text to suggested administration times."""
    freq = frequency.lower()
    if any(w in freq for w in ("twice", "bid", "b.i.d", "2x")):
        return ["08:00", "20:00"]
    if any(w in freq for w in ("three", "tid", "t.i.d", "3x")):
        return ["08:00", "14:00", "20:00"]
    if any(w in freq for w in ("four", "qid", "q.i.d", "4x")):
        return ["08:00", "12:00", "18:00", "22:00"]
    if any(w in freq for w in ("night", "bedtime", "hs", "qhs")):
        return ["22:00"]
    if any(w in freq for w in ("morning", "am", "once")):
        return ["08:00"]
    return ["09:00"]


def build_care_plan(
    entities: Dict[str, Any],
    age: int,
    condition: str | None = None,
) -> List[Dict[str, str]]:
    care_plan: List[Dict[str, str]] = [
        {"time": "07:00", "activity": "Wake up, drink 1–2 glasses of water, note any overnight symptoms."},
        {"time": "08:00", "activity": "Breakfast as advised by physician. Do not skip meals if on medication."},
    ]

    for med in entities.get("medicines", []):
        for t in _med_times(med.get("frequency", "")):
            care_plan.append(
                {
                    "time": t,
                    "activity": f"Take {med['name']} {med['dose']} — {med['frequency']}.",
                }
            )

    care_plan.extend(
        [
            {"time": "13:00", "activity": "Light walk (10–20 min) if clinically appropriate. Avoid strenuous activity unless cleared by doctor."},
            {"time": "15:00", "activity": "Hydration check — target 8 glasses of water daily unless fluid restriction applies."},
            {"time": "18:00", "activity": "Review medicines taken today; note any missed doses or side effects."},
            {"time": "21:00", "activity": "Prepare for sleep — no screens 30 min before bed; note symptoms in journal."},
        ]
    )

    if age > 60:
        care_plan.append({"time": "20:00", "activity": "Family or caregiver check-in — share today's symptom notes."})
    if condition:
        cond_lower = condition.lower()
        if "diabet" in cond_lower:
            care_plan.append({"time": "07:30", "activity": f"Diabetes check: measure fasting blood glucose before breakfast."})
        elif "hypertens" in cond_lower or "bp" in cond_lower or "blood pressure" in cond_lower:
            care_plan.append({"time": "07:30", "activity": f"Hypertension check: measure blood pressure before medicines."})
        else:
            care_plan.append({"time": "14:00", "activity": f"Condition focus ({condition}): self-monitoring as instructed by doctor."})

    # Sort by time and deduplicate
    seen: set = set()
    unique_plan: List[Dict[str, str]] = []
    for entry in sorted(care_plan, key=lambda x: x["time"]):
        key = (entry["time"], entry["activity"][:30])
        if key not in seen:
            seen.add(key)
            unique_plan.append(entry)
    return unique_plan[:12]


def build_reminders(entities: Dict[str, Any]) -> List[Dict[str, str]]:
    now = datetime.utcnow()
    reminders: List[Dict[str, str]] = []
    for i, med in enumerate(entities.get("medicines", [])[:5]):
        reminders.append(
            {
                "message": f"Medication reminder: {med['name']} {med['dose']}",
                "remind_at": (now + timedelta(hours=i + 1)).isoformat(),
            }
        )
    if not reminders:
        reminders.append(
            {
                "message": "General care reminder: review your care plan and hydration.",
                "remind_at": (now + timedelta(hours=2)).isoformat(),
            }
        )
    return reminders


_DIAGNOSIS_FLAGS: Dict[str, str] = {
    "diabet": "Sudden very high or very low blood sugar (sweating, confusion, shakiness) — seek emergency care.",
    "hypertens": "Severe headache with blurred vision or nosebleed — may signal hypertensive crisis.",
    "cardiac": "New or worsening chest pain, rapid irregular heartbeat, or sudden shortness of breath.",
    "heart": "New or worsening chest pain, rapid irregular heartbeat, or sudden shortness of breath.",
    "kidney": "Drastically reduced urine output, severe swelling of legs/ankles, or sudden back pain.",
    "renal": "Drastically reduced urine output, severe swelling of legs/ankles, or sudden back pain.",
    "asthma": "Rescue inhaler not relieving breathlessness within 15 minutes — go to emergency.",
    "pneumonia": "Oxygen level below 94%, persistent high fever, or bluish lips — call emergency.",
    "liver": "Yellowing of skin or eyes (jaundice), dark urine, or sudden abdominal pain.",
}


def build_red_flags(entities: Dict[str, Any]) -> List[str]:
    flags = [
        "Severe chest pain, breathing difficulty, or sudden confusion — call emergency immediately.",
        "Persistent high fever (> 38.5 °C / 101.3 °F), repeated vomiting, or inability to take medicines.",
        "Symptoms worsening significantly despite taking treatment for 24–48 hours.",
        "New swelling, rash, or difficulty breathing after starting a new medication (possible allergic reaction).",
    ]
    for diagnosis in entities.get("diagnoses", []):
        d_lower = diagnosis.lower()
        for keyword, flag in _DIAGNOSIS_FLAGS.items():
            if keyword in d_lower and flag not in flags:
                flags.append(f"[{diagnosis}] {flag}")
                break
    if not entities.get("diagnoses"):
        flags.append("Consult your doctor if any new or unexpected symptom appears after discharge.")
    return flags


def _deterministic_summary(text: str, entities: Dict[str, Any]) -> str:
    diagnoses = entities.get("diagnoses", [])
    medicines = entities.get("medicines", [])
    follow_up = entities.get("follow_up", [])
    tests = entities.get("tests", [])

    diagnosis_part = (
        f"Main reported condition(s): {', '.join(diagnoses)}."
        if diagnoses
        else "Main condition is not clearly stated in the extracted text."
    )
    meds_part = (
        "Detected medicines: "
        + ", ".join(f"{m['name']} {m['dose']} ({m['frequency']})" for m in medicines[:4])
        + "."
        if medicines
        else "No medicine name was confidently extracted; please confirm your exact medicines and timing with your doctor."
    )
    follow_up_part = (
        f"Follow-up note: {follow_up[0]}."
        if follow_up
        else "No clear follow-up date was detected; confirm a follow-up time with your doctor."
    )
    tests_part = f"Tests mentioned: {', '.join(tests)}." if tests else "No specific test names were clearly detected."
    safety_part = "Seek urgent medical care for severe chest pain, breathing difficulty, confusion, or persistent worsening symptoms."
    return " ".join([diagnosis_part, meds_part, follow_up_part, tests_part, safety_part])


def _sanitize_summary(summary: str, fallback_summary: str) -> str:
    if not summary:
        return fallback_summary

    banned_phrases = [
        "i'm having trouble reading",
        "i am having trouble reading",
        "information isn't clear",
        "can you tell me",
        "i need to ask you",
    ]
    lowered = summary.lower()
    if any(phrase in lowered for phrase in banned_phrases):
        return fallback_summary
    return summary


def _translate_stub_to_urdu(text: str, entities: Dict[str, Any]) -> str:
    # Lightweight fallback for hackathon demo when no multilingual model is connected.
    med_count = len(entities.get("medicines", []))
    followup_found = "ہاں" if entities.get("follow_up") else "نہیں"
    return (
        "اردو خلاصہ (خودکار):\n"
        "یہ رپورٹ آپ کی صحت کی معلومات کو آسان الفاظ میں پیش کرتی ہے۔ "
        "دوائیں وقت پر لیں، پانی مناسب مقدار میں پئیں، اور علامات کا روزانہ جائزہ لیں۔\n"
        f"شناخت شدہ ادویات کی تعداد: {med_count}۔ فالو اپ ہدایت ملی: {followup_found}۔\n"
        "اگر سانس میں تکلیف، سینے میں شدید درد، الجھن، یا علامات میں بگاڑ ہو تو فوری ڈاکٹر سے رابطہ کریں۔\n\n"
        f"English summary excerpt: {text[:240]}"
    )
