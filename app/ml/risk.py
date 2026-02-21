from typing import Any, Dict, List, Tuple


def compute_risk_score(entities: Dict[str, Any], age: int) -> Tuple[str, List[str]]:
    score = 0
    factors: List[str] = []

    med_count = len(entities.get("medicines", []))
    if med_count >= 4:
        score += 2
        factors.append("Polypharmacy (4+ medicines) may reduce adherence.")
    elif med_count >= 2:
        score += 1
        factors.append("Multiple medicines require schedule discipline.")

    if age >= 65:
        score += 1
        factors.append("Older age can increase follow-up and adherence complexity.")

    if not entities.get("follow_up"):
        score += 1
        factors.append("No clear follow-up instruction detected in report.")

    if score >= 4:
        return "high", factors
    if score >= 2:
        return "medium", factors
    return "low", factors or ["Limited risk indicators from available report text."]
