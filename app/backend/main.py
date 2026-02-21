import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.backend.config import get_settings
from app.backend.db import (
    get_due_reminders,
    get_metric_summary,
    get_stats,
    get_upload,
    init_db,
    mark_reminder_sent,
    save_chat,
    save_metric,
    save_reminder,
    save_upload,
)
from app.backend.logging_config import setup_logging
from app.backend.handout import build_patient_handout_pdf
from app.backend.metrics import citation_coverage, estimate_readability_score, grounded_answer
from app.backend.schemas import (
    AdminInsightsResponse,
    AdherenceSimulationRequest,
    AdherenceSimulationResponse,
    ChatRequest,
    ChatResponse,
    ProcessResponse,
    StatsResponse,
)
from app.ml.advanced_features import (
    build_recovery_scorecard,
    generate_doctor_questions,
    medication_safety_scan,
    simulate_adherence_impact,
)
from app.ml.llm import get_llm_provider
from app.ml.parser import extract_entities, extract_text
from app.ml.recommender import DISCLAIMER, build_care_plan, build_red_flags, build_reminders, generate_patient_summary
from app.ml.risk import compute_risk_score
from app.rag.retriever import retrieve_context

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="CarePath AI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    scheduler.add_job(_reminder_worker, "interval", seconds=30, id="reminder-worker", replace_existing=True)
    scheduler.start()
    logger.info("CarePath AI backend started")


@app.on_event("shutdown")
def shutdown_event() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.post("/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile = File(...),
    age: int = Form(40),
    condition: str = Form(""),
    language_preference: str = Form("both"),
) -> ProcessResponse:
    start = time.perf_counter()
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Missing filename")
    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    safe_name = Path(file.filename).name
    upload_path = Path(settings.uploads_dir) / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    upload_path.write_bytes(content)

    extracted_text = extract_text(safe_name, content)
    if not extracted_text.strip():
        extracted_text = "No meaningful text was detected. Please provide a clearer report."

    entities = extract_entities(extracted_text)
    summary_en, summary_ur = generate_patient_summary(extracted_text, entities)
    care_plan = build_care_plan(entities, age=age, condition=condition or None)
    reminders = build_reminders(entities)
    red_flags = build_red_flags(entities)
    risk_score, risk_factors = compute_risk_score(entities, age=age)
    safety_alerts = medication_safety_scan(entities)
    recovery_scorecard = build_recovery_scorecard(entities, age=age, risk_score=risk_score)
    doctor_questions = generate_doctor_questions(entities, condition or None)
    readability = estimate_readability_score(summary_en)

    upload_payload: Dict[str, Any] = {
        "filename": safe_name,
        "file_path": str(upload_path),
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

    return ProcessResponse(
        upload_id=upload_id,
        filename=safe_name,
        parsed_text_excerpt=extracted_text[:500],
        entities=entities,
        summary_en=summary_en,
        summary_ur=summary_ur,
        care_plan=care_plan,
        reminders=reminders,
        red_flags=red_flags,
        risk_score=risk_score,
        risk_factors=risk_factors,
        safety_alerts=safety_alerts,
        recovery_scorecard=recovery_scorecard,
        doctor_questions=doctor_questions,
        disclaimer=DISCLAIMER,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    try:
        upload = get_upload(req.upload_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    context, citations = retrieve_context(req.question, upload["extracted_text"])
    prompt = (
        "You are CarePath AI. Only answer using provided context.\n"
        "If answer is not found, clearly say so.\n\n"
        f"Question: {req.question}\n\nContext:\n{context}\n\n"
        f"Disclaimer: {DISCLAIMER}"
    )
    generated = get_llm_provider().generate(prompt)
    answer = grounded_answer(citations, generated)
    coverage = citation_coverage(req.question, citations)
    latency_ms = (time.perf_counter() - start) * 1000
    save_metric("chat_latency_ms", latency_ms, f"upload:{req.upload_id}")
    save_metric("chat_citation_coverage", coverage, f"upload:{req.upload_id}")
    save_chat(req.upload_id, req.question, answer, citations)
    return ChatResponse(answer=answer, citations=citations)


@app.get("/admin/stats", response_model=StatsResponse)
def admin_stats() -> StatsResponse:
    uploads, chats, reminders = get_stats()
    return StatsResponse(total_uploads=uploads, total_chats=chats, total_reminders=reminders)


@app.get("/admin/insights", response_model=AdminInsightsResponse)
def admin_insights() -> AdminInsightsResponse:
    uploads, chats, reminders = get_stats()
    avg_metrics = get_metric_summary()
    return AdminInsightsResponse(
        total_uploads=uploads,
        total_chats=chats,
        total_reminders=reminders,
        avg_metrics=avg_metrics,
    )


@app.post("/simulate/adherence", response_model=AdherenceSimulationResponse)
def simulate_adherence(req: AdherenceSimulationRequest) -> AdherenceSimulationResponse:
    try:
        upload = get_upload(req.upload_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    outcome = simulate_adherence_impact(upload["risk_score"], req.adherence_percent)
    save_metric("adherence_simulation_percent", float(req.adherence_percent), f"upload:{req.upload_id}")
    return AdherenceSimulationResponse(**outcome)


@app.get("/export/handout/{upload_id}")
def export_handout(upload_id: int) -> Response:
    try:
        upload = get_upload(upload_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pdf_bytes = build_patient_handout_pdf(upload)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="carepath_handout_{upload_id}.pdf"'},
    )


def _reminder_worker() -> None:
    now = datetime.utcnow().isoformat()
    rows = get_due_reminders(now)
    for row in rows:
        logger.info("Reminder due: upload=%s msg=%s", row["upload_id"], row["message"])
        mark_reminder_sent(int(row["id"]))
