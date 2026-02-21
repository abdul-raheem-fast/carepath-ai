from app.ml.parser import extract_entities


def test_extract_entities_detects_core_fields() -> None:
    text = (
        "Diagnosis: diabetes. Metformin 500 mg twice daily. "
        "Amlodipine 5 mg once daily. Follow-up in 2 weeks. Test: HbA1c."
    )
    entities = extract_entities(text)
    assert "medicines" in entities
    assert len(entities["medicines"]) >= 1
    assert "follow_up" in entities
