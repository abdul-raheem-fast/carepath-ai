from app.ml.recommender import build_care_plan


def test_build_care_plan_has_entries() -> None:
    entities = {
        "medicines": [
            {"name": "Metformin", "dose": "500 mg", "frequency": "twice daily"},
        ]
    }
    plan = build_care_plan(entities, age=50, condition="diabetes")
    assert len(plan) >= 4
    assert any("Metformin" in row["activity"] for row in plan)
