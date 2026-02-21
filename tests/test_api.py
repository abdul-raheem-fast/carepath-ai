from fastapi.testclient import TestClient

from app.backend.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_admin_insights_endpoint() -> None:
    response = client.get("/admin/insights")
    assert response.status_code == 200
    payload = response.json()
    assert "total_uploads" in payload
    assert "avg_metrics" in payload


def test_process_and_adherence_simulation() -> None:
    content = (
        "Diagnosis diabetes. Metformin 500 mg twice daily. "
        "Amlodipine 5 mg once daily. Follow-up in 2 weeks."
    )
    files = {"file": ("synthetic.txt", content.encode("utf-8"), "text/plain")}
    data = {"age": 55, "condition": "diabetes", "language_preference": "both"}

    process_resp = client.post("/process", files=files, data=data)
    assert process_resp.status_code == 200
    payload = process_resp.json()
    assert "safety_alerts" in payload
    assert "recovery_scorecard" in payload
    assert "doctor_questions" in payload

    sim_resp = client.post(
        "/simulate/adherence",
        json={"upload_id": payload["upload_id"], "adherence_percent": 85},
    )
    assert sim_resp.status_code == 200
    sim_payload = sim_resp.json()
    assert sim_payload["projected_risk"] in {"low", "medium", "high"}

    handout_resp = client.get(f"/export/handout/{payload['upload_id']}")
    assert handout_resp.status_code == 200
    assert handout_resp.headers["content-type"].startswith("application/pdf")
    assert handout_resp.content[:4] == b"%PDF"
