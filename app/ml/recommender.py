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


def build_care_plan(
    entities: Dict[str, Any],
    age: int,
    condition: str | None = None,
) -> List[Dict[str, str]]:
    care_plan: List[Dict[str, str]] = [
        {"time": "07:00", "activity": "Wake up, hydrate, check symptoms briefly."},
        {"time": "08:00", "activity": "Breakfast as advised by physician."},
    ]

    for med in entities.get("medicines", []):
        care_plan.append(
            {
                "time": "09:00",
                "activity": f"Take {med['name']} {med['dose']} ({med['frequency']}).",
            }
        )

    care_plan.extend(
        [
            {"time": "13:00", "activity": "Light walk (10-20 min) if clinically appropriate."},
            {"time": "18:00", "activity": "Review medicines and water intake."},
            {"time": "21:00", "activity": "Sleep preparation and symptom notes."},
        ]
    )

    if age > 60:
        care_plan.append({"time": "20:00", "activity": "Family/caregiver check-in reminder."})
    if condition:
        care_plan.append({"time": "14:00", "activity": f"Condition focus: {condition} self-monitoring."})
    return care_plan[:10]


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


def build_red_flags(entities: Dict[str, Any]) -> List[str]:
    flags = [
        "Severe chest pain, breathing difficulty, or confusion.",
        "Persistent fever, repeated vomiting, or inability to take medicines.",
        "Worsening symptoms despite treatment for 24-48 hours.",
    ]
    if entities.get("diagnoses"):
        flags.append("Any diagnosis-specific warning from your doctor should trigger immediate contact.")
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
