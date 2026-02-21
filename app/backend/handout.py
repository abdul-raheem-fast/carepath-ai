"""
CarePath AI – Patient Handout PDF Generator
Professional design using ReportLab Platypus with proper Urdu (RTL) rendering.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.ml.advanced_features import build_recovery_scorecard, generate_doctor_questions, medication_safety_scan
from app.ml.recommender import DISCLAIMER


# ── Colour palette ─────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1a3c5e")
BRAND_MID    = colors.HexColor("#2d6a9f")
BRAND_LIGHT  = colors.HexColor("#e3f2fd")
GREEN        = colors.HexColor("#2e7d32")
GREEN_BG     = colors.HexColor("#e8f5e9")
RED          = colors.HexColor("#c62828")
RED_BG       = colors.HexColor("#fce4ec")
AMBER        = colors.HexColor("#e65100")
AMBER_BG     = colors.HexColor("#fff8e1")
PURPLE       = colors.HexColor("#6a1b9a")
PURPLE_BG    = colors.HexColor("#f3e5f5")
TEAL         = colors.HexColor("#00695c")
TEAL_BG      = colors.HexColor("#e0f2f1")
GREY_TEXT    = colors.HexColor("#546e7a")
DIVIDER      = colors.HexColor("#e0e0e0")
WHITE        = colors.white
BLACK        = colors.black


def _urdu_render(text: str) -> str:
    """
    Apply Arabic reshaping + bidi for Urdu RTL text.
    Returns empty string if no Arabic-capable font is embedded,
    so callers can fall back gracefully to English-only.
    """
    if not text.strip():
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return ""


def _safe_ur(text: str) -> str:
    """Strip the English echo part that the Urdu stub appends."""
    clean = text.split("English summary excerpt:")[0]
    clean = clean.replace("اردو خلاصہ (خودکار):", "").strip()
    return clean


def _styles() -> dict:
    base = getSampleStyleSheet()
    s: dict = {}

    def ps(name: str, **kw: Any) -> ParagraphStyle:
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    s["cover_title"]    = ps("CoverTitle",    fontSize=26, textColor=WHITE,     alignment=TA_CENTER, leading=34, fontName="Helvetica-Bold")
    s["cover_sub"]      = ps("CoverSub",      fontSize=12, textColor=WHITE,     alignment=TA_CENTER, leading=18, fontName="Helvetica")
    s["section_hdr"]    = ps("SectionHdr",    fontSize=13, textColor=BRAND_DARK, leading=18, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4)
    s["body"]           = ps("Body",          fontSize=10, textColor=BLACK,      leading=16, fontName="Helvetica", spaceAfter=4)
    s["body_bold"]      = ps("BodyBold",      fontSize=10, textColor=BLACK,      leading=16, fontName="Helvetica-Bold")
    s["bullet"]         = ps("Bullet",        fontSize=10, textColor=BLACK,      leading=15, fontName="Helvetica", leftIndent=12, bulletIndent=0, spaceAfter=3)
    s["urdu"]           = ps("Urdu",          fontSize=12, textColor=BLACK,      leading=22, alignment=TA_RIGHT, fontName="Helvetica")
    s["disclaimer"]     = ps("Disclaimer",    fontSize=9,  textColor=AMBER,      leading=14, fontName="Helvetica-Oblique", alignment=TA_CENTER)
    s["table_hdr"]      = ps("TableHdr",      fontSize=9,  textColor=WHITE,      fontName="Helvetica-Bold", alignment=TA_CENTER)
    s["table_cell"]     = ps("TableCell",     fontSize=9,  textColor=BLACK,      fontName="Helvetica",      leading=13)
    s["badge_low"]      = ps("BadgeLow",      fontSize=10, textColor=GREEN,      fontName="Helvetica-Bold", alignment=TA_CENTER)
    s["badge_med"]      = ps("BadgeMed",      fontSize=10, textColor=AMBER,      fontName="Helvetica-Bold", alignment=TA_CENTER)
    s["badge_high"]     = ps("BadgeHigh",     fontSize=10, textColor=RED,        fontName="Helvetica-Bold", alignment=TA_CENTER)
    s["footer"]         = ps("Footer",        fontSize=8,  textColor=GREY_TEXT,  alignment=TA_CENTER)
    return s


def _section_header(text: str, color: colors.Color, styles: dict) -> List[Any]:
    """Coloured bar section header with rule."""
    p = Paragraph(f"<b>{text}</b>", ParagraphStyle(
        "SH", fontSize=11, textColor=WHITE, alignment=TA_LEFT,
        fontName="Helvetica-Bold", leading=16,
        backColor=color, leftPadding=8, rightPadding=8,
        topPadding=5, bottomPadding=5, borderRadius=4,
    ))
    return [Spacer(1, 6 * mm), p, Spacer(1, 3 * mm)]


def _bullet_items(items: List[str], styles: dict, bullet: str = "•") -> List[Paragraph]:
    return [Paragraph(f"{bullet}  {item}", styles["bullet"]) for item in items]


def _info_box(content_rows: List[List[Any]], bg: colors.Color, border: colors.Color) -> Table:
    t = Table(content_rows, colWidths=["100%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), bg),
        ("ROUNDEDCORNERS", [6]),
        ("BOX",         (0, 0), (-1, -1), 1, border),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _score_bar_table(label: str, value: int, color: colors.Color, styles: dict) -> Table:
    """Render a labelled progress bar as a two-row table."""
    filled = max(0, min(100, value))
    empty  = 100 - filled
    bar_data = [[""]]
    bar = Table(bar_data, colWidths=[filled * mm * 1.58 if filled else 0.5 * mm, empty * mm * 1.58 if empty else 0.5 * mm], rowHeights=[7])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color),
        ("BACKGROUND", (1, 0), (1, 0), DIVIDER),
        ("ROUNDEDCORNERS", [4]),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    outer = Table([
        [Paragraph(f"<b>{label}</b>", styles["body"]), Paragraph(f"<b>{value}/100</b>", ParagraphStyle("V", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold"))],
        [bar, ""],
    ], colWidths=[120 * mm, 40 * mm])
    outer.setStyle(TableStyle([
        ("SPAN",          (0, 1), (1, 1)),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return outer


def _on_page(canvas: Any, doc: Any) -> None:
    """Footer + page number on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY_TEXT)
    canvas.drawString(15 * mm, 8 * mm, "CarePath AI — Not a medical diagnosis; consult a licensed doctor.")
    canvas.drawRightString(A4[0] - 15 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ── Main builder ──────────────────────────────────────────────────────────────
def build_patient_handout_pdf(upload: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = _styles()
    story: List[Any] = []

    entities    = upload.get("entities", {})
    risk_score  = upload.get("risk_score", "medium")
    summary_en  = upload.get("summary_en", "Summary not available.")
    summary_ur  = _safe_ur(upload.get("summary_ur", ""))
    care_plan   = upload.get("care_plan", [])
    risk_factors = upload.get("risk_factors", [])
    red_flags   = upload.get("red_flags", [])
    reminders   = upload.get("reminders", [])

    safety_alerts   = medication_safety_scan(entities)
    recovery        = build_recovery_scorecard(entities, age=40, risk_score=risk_score)
    doctor_questions = generate_doctor_questions(entities, None)

    # ── COVER ──────────────────────────────────────────────────────────────
    cover_data = [[
        Paragraph("🏥  CarePath AI", styles["cover_title"]),
    ], [
        Paragraph("Patient Care Handout", styles["cover_sub"]),
    ], [
        Paragraph(f"Generated: {datetime.utcnow().strftime('%B %d, %Y  %H:%M UTC')}", styles["cover_sub"]),
    ], [
        Paragraph(f"Upload ID: {upload.get('id', 'N/A')}  •  File: {upload.get('filename', 'N/A')}", styles["cover_sub"]),
    ]]
    cover_table = Table(cover_data, colWidths=[doc.width])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [BRAND_DARK]),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("ROUNDEDCORNERS", [10]),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 8 * mm))

    # ── SECTION: Bilingual Summary ─────────────────────────────────────────
    story += _section_header("📋  Patient Summary", TEAL, styles)

    # English summary always shown
    story.append(_info_box(
        [[Paragraph("<b>English Summary</b>", styles["body_bold"])],
         [Paragraph(summary_en, styles["body"])]],
        TEAL_BG, TEAL,
    ))
    story.append(Spacer(1, 4 * mm))

    # Urdu summary — show transliterated clean text; note full Urdu in web app
    ur_note_style = ParagraphStyle(
        "UrNote", fontSize=10, textColor=TEAL, fontName="Helvetica-Oblique",
        leading=16, alignment=TA_LEFT,
    )
    ur_lines = [l.strip() for l in summary_ur.split("\n") if l.strip() and not any(
        x in l for x in ["English summary excerpt:", "English source excerpt:"]
    )]
    # Only include lines that are pure ASCII (skip unrenderable Urdu glyph lines)
    ascii_lines = [l for l in ur_lines if all(ord(c) < 128 for c in l)]
    urdu_section_content = [
        [Paragraph("<b>Urdu Summary (اردو خلاصہ)</b>", styles["body_bold"])],
        [Paragraph(
            "Full Urdu summary is displayed in the CarePath AI web app with proper Urdu font rendering.",
            ur_note_style,
        )],
    ]
    if ascii_lines:
        urdu_section_content.append([Paragraph(" ".join(ascii_lines[:3]), styles["body"])])
    story.append(_info_box(urdu_section_content, BRAND_LIGHT, BRAND_MID))

    # ── SECTION: Daily Care Plan ──────────────────────────────────────────
    story += _section_header("📅  Personalized Daily Care Plan", BRAND_MID, styles)

    plan_header = ["Time", "Activity"]
    plan_data = [[Paragraph(plan_header[0], styles["table_hdr"]), Paragraph(plan_header[1], styles["table_hdr"])]]
    for row in care_plan:
        plan_data.append([
            Paragraph(f"⏰ {row.get('time', '--')}", styles["table_cell"]),
            Paragraph(row.get("activity", ""), styles["table_cell"]),
        ])

    plan_table = Table(plan_data, colWidths=[35 * mm, 140 * mm])
    plan_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, DIVIDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(plan_table)

    # ── SECTION: Risk Assessment ──────────────────────────────────────────
    story += _section_header("⚡  Risk Assessment & Explainability", AMBER, styles)

    risk_color_map = {"low": GREEN, "medium": AMBER, "high": RED}
    risk_bg_map    = {"low": GREEN_BG, "medium": AMBER_BG, "high": RED_BG}
    rc = risk_color_map.get(risk_score.lower(), GREY_TEXT)
    rbg = risk_bg_map.get(risk_score.lower(), WHITE)

    risk_badge = Table([[Paragraph(f"Risk Level: <b>{risk_score.upper()}</b>", ParagraphStyle(
        "RB", fontSize=14, textColor=rc, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=20
    ))]], colWidths=[doc.width])
    risk_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rbg),
        ("BOX",        (0, 0), (-1, -1), 1.5, rc),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [8]),
    ]))
    story.append(risk_badge)
    story.append(Spacer(1, 4 * mm))
    if risk_factors:
        story.append(Paragraph("<b>Explainability Factors:</b>", styles["body_bold"]))
        story += _bullet_items(risk_factors, styles)

    # ── SECTION: Recovery Scorecard ───────────────────────────────────────
    story += _section_header("📈  Recovery Scorecard", PURPLE, styles)

    score_colors = [BRAND_MID, GREEN, AMBER, PURPLE]
    score_labels = ["Overall Recovery Readiness", "Adherence Readiness", "Follow-up Clarity", "Monitoring Strength"]
    score_values = [
        recovery["overall_recovery_readiness"],
        recovery["adherence_readiness"],
        recovery["followup_clarity"],
        recovery["monitoring_strength"],
    ]
    for lbl, val, clr in zip(score_labels, score_values, score_colors):
        story.append(_score_bar_table(lbl, val, clr, styles))
        story.append(Spacer(1, 2 * mm))

    # ── SECTION: Red-Flag Warnings ────────────────────────────────────────
    story += _section_header("🚨  Red-Flag Warnings", RED, styles)
    story.append(_info_box(
        [[Paragraph(f"⚠️  {flag}", styles["bullet"])] for flag in red_flags],
        RED_BG, RED,
    ))

    # ── SECTION: Medication Safety ────────────────────────────────────────
    story += _section_header("💊  Medication Safety Alerts", AMBER, styles)
    if safety_alerts:
        story += _bullet_items(safety_alerts, styles, bullet="⚠️")
    else:
        story.append(Paragraph("✅  No medication safety conflicts detected.", styles["body"]))

    # ── SECTION: Clinical Entities ────────────────────────────────────────
    story += _section_header("🔬  Extracted Clinical Entities", TEAL, styles)

    meds = entities.get("medicines", [])
    diag = entities.get("diagnoses", [])
    tests = entities.get("tests", [])
    followup = entities.get("follow_up", [])

    entity_data = [
        [Paragraph("<b>Medicines</b>", styles["table_hdr"]),
         Paragraph("<b>Diagnoses</b>", styles["table_hdr"]),
         Paragraph("<b>Tests</b>", styles["table_hdr"]),
         Paragraph("<b>Follow-up</b>", styles["table_hdr"])],
    ]
    max_rows = max(len(meds), len(diag), len(tests), len(followup), 1)
    for i in range(max_rows):
        med_cell  = f"💊 {meds[i]['name']} {meds[i]['dose']}" if i < len(meds) else ""
        diag_cell = f"📋 {diag[i]}" if i < len(diag) else ""
        test_cell = f"🧪 {tests[i]}" if i < len(tests) else ""
        fu_cell   = f"📅 {followup[i]}" if i < len(followup) else ""
        entity_data.append([
            Paragraph(med_cell,  styles["table_cell"]),
            Paragraph(diag_cell, styles["table_cell"]),
            Paragraph(test_cell, styles["table_cell"]),
            Paragraph(fu_cell,   styles["table_cell"]),
        ])

    ent_table = Table(entity_data, colWidths=[doc.width / 4] * 4)
    ent_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, DIVIDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(ent_table)

    # ── SECTION: Reminders ────────────────────────────────────────────────
    story += _section_header("⏰  Upcoming Reminders", BRAND_MID, styles)
    for r in reminders:
        when = r.get("remind_at", "")[:16].replace("T", " ")
        story.append(Paragraph(f"🔔  <b>{r.get('message', '')}</b> — {when} UTC", styles["bullet"]))

    # ── SECTION: Doctor Questions ─────────────────────────────────────────
    story += _section_header("🩺  Questions to Ask Your Doctor", PURPLE, styles)
    story.append(_info_box(
        [[Paragraph(f"❓  {q}", styles["bullet"])] for q in doctor_questions],
        PURPLE_BG, PURPLE,
    ))

    # ── FOOTER DISCLAIMER ─────────────────────────────────────────────────
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=DIVIDER))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"⚕️  {DISCLAIMER}", styles["disclaimer"]))
    story.append(Paragraph("CarePath AI — Powered by Groq Llama 3.1 | For educational purposes only.", styles["footer"]))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buffer.seek(0)
    return buffer.getvalue()
