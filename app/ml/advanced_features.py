from typing import Any, Dict, List


def medication_safety_scan(entities: Dict[str, Any]) -> List[str]:
    medicines = entities.get("medicines", [])
    alerts: List[str] = []
    names = [m.get("name", "").lower() for m in medicines]
    doses = [m.get("dose", "").lower() for m in medicines]

    duplicate_names = {n for n in names if n and names.count(n) > 1}
    if duplicate_names:
        alerts.append("Potential duplicate medication names detected. Verify regimen with doctor/pharmacist.")

    if any("mg" in d and any(x in d for x in ["1000", "1200", "1500"]) for d in doses):
        alerts.append("One or more high-dose entries detected. Confirm dose timing and safety instructions.")

    if len(medicines) >= 5:
        alerts.append("Complex medication schedule (5+ medicines). Consider pillbox/reminder supervision.")

    if not alerts:
        alerts.append("No obvious medication safety conflicts detected from extracted text.")
    return alerts


def build_recovery_scorecard(entities: Dict[str, Any], age: int, risk_score: str) -> Dict[str, Any]:
    med_count = len(entities.get("medicines", []))
    has_follow_up = bool(entities.get("follow_up"))
    has_tests = bool(entities.get("tests"))

    adherence_readiness = max(30, 95 - (med_count * 10) - (10 if age >= 65 else 0))
    followup_clarity = 90 if has_follow_up else 45
    monitoring_strength = 85 if has_tests else 55
    risk_penalty = {"low": 5, "medium": 20, "high": 35}.get(risk_score, 20)
    overall = int(max(20, min(95, (adherence_readiness + followup_clarity + monitoring_strength) / 3 - risk_penalty / 4)))

    return {
        "overall_recovery_readiness": overall,
        "adherence_readiness": int(adherence_readiness),
        "followup_clarity": int(followup_clarity),
        "monitoring_strength": int(monitoring_strength),
    }


def generate_doctor_questions(entities: Dict[str, Any], condition: str | None = None) -> List[str]:
    questions = [
        "Which symptom should make me seek urgent medical care immediately?",
        "Can you confirm exact timing for each medicine and whether to take with food?",
        "What should I do if I miss a dose?",
    ]
    if entities.get("follow_up"):
        questions.append("Is my current follow-up date sufficient or should I come earlier if symptoms persist?")
    else:
        questions.append("When should my next follow-up visit be scheduled?")

    if condition:
        questions.append(f"What daily self-monitoring should I do at home for {condition}?")
    if entities.get("tests"):
        questions.append("How will upcoming test results change my treatment plan?")
    return questions[:6]


def simulate_adherence_impact(risk_score: str, adherence_percent: int) -> Dict[str, Any]:
    if adherence_percent >= 85:
        projected = "low" if risk_score != "high" else "medium"
        benefits = [
            "Lower chance of avoidable readmission.",
            "Better symptom control with consistent routine.",
        ]
    elif adherence_percent >= 60:
        projected = "medium"
        benefits = [
            "Partial improvement expected, but missed doses still increase instability.",
            "Follow-up and reminders become critical in this range.",
        ]
    else:
        projected = "high"
        benefits = [
            "High likelihood of treatment interruption effects.",
            "Increased risk of symptom worsening and urgent visits.",
        ]

    coaching = [
        "Use fixed alarm times linked to meals/prayer/work breaks.",
        "Track medicines on a one-page checklist daily.",
        "Ask family/caregiver for evening adherence check-ins.",
    ]
    return {
        "adherence_percent": adherence_percent,
        "projected_risk": projected,
        "expected_benefits": benefits,
        "coaching_tips": coaching,
    }
