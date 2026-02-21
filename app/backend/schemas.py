from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
    age: int = Field(default=40, ge=0, le=120)
    language_preference: str = "both"
    condition: Optional[str] = None


class ProcessResponse(BaseModel):
    upload_id: int
    filename: str
    parsed_text_excerpt: str
    entities: Dict[str, Any]
    summary_en: str
    summary_ur: str
    care_plan: List[Dict[str, str]]
    reminders: List[Dict[str, str]]
    red_flags: List[str]
    risk_score: str
    risk_factors: List[str]
    safety_alerts: List[str]
    recovery_scorecard: Dict[str, Any]
    doctor_questions: List[str]
    disclaimer: str


class ChatRequest(BaseModel):
    upload_id: int
    question: str


class ChatResponse(BaseModel):
    answer: str
    citations: List[str]


class ReminderCreate(BaseModel):
    upload_id: int
    message: str
    remind_at: datetime


class StatsResponse(BaseModel):
    total_uploads: int
    total_chats: int
    total_reminders: int


class AdminInsightsResponse(BaseModel):
    total_uploads: int
    total_chats: int
    total_reminders: int
    avg_metrics: Dict[str, float]


class AdherenceSimulationRequest(BaseModel):
    upload_id: int
    adherence_percent: int = Field(ge=0, le=100)


class AdherenceSimulationResponse(BaseModel):
    adherence_percent: int
    projected_risk: str
    expected_benefits: List[str]
    coaching_tips: List[str]
