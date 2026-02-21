import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Tuple

from app.backend.config import get_settings


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                entities_json TEXT NOT NULL,
                summary_en TEXT NOT NULL,
                summary_ur TEXT NOT NULL,
                care_plan_json TEXT NOT NULL,
                reminders_json TEXT NOT NULL,
                red_flags_json TEXT NOT NULL,
                risk_score TEXT NOT NULL,
                risk_factors_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                citations_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(upload_id) REFERENCES uploads(id)
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                sent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(upload_id) REFERENCES uploads(id)
            );

            CREATE TABLE IF NOT EXISTS eval_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                context TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def save_upload(payload: Dict[str, Any]) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO uploads (
                filename, file_path, extracted_text, entities_json, summary_en, summary_ur,
                care_plan_json, reminders_json, red_flags_json, risk_score, risk_factors_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["filename"],
                payload["file_path"],
                payload["extracted_text"],
                json.dumps(payload["entities"]),
                payload["summary_en"],
                payload["summary_ur"],
                json.dumps(payload["care_plan"]),
                json.dumps(payload["reminders"]),
                json.dumps(payload["red_flags"]),
                payload["risk_score"],
                json.dumps(payload["risk_factors"]),
                datetime.utcnow().isoformat(),
            ),
        )
        return int(cursor.lastrowid)


def get_upload(upload_id: int) -> Dict[str, Any]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
    if not row:
        raise ValueError(f"Upload id {upload_id} not found")

    return {
        "id": int(row["id"]),
        "filename": row["filename"],
        "file_path": row["file_path"],
        "extracted_text": row["extracted_text"],
        "entities": json.loads(row["entities_json"]),
        "summary_en": row["summary_en"],
        "summary_ur": row["summary_ur"],
        "care_plan": json.loads(row["care_plan_json"]),
        "reminders": json.loads(row["reminders_json"]),
        "red_flags": json.loads(row["red_flags_json"]),
        "risk_score": row["risk_score"],
        "risk_factors": json.loads(row["risk_factors_json"]),
    }


def save_chat(upload_id: int, question: str, answer: str, citations: List[str]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_logs (upload_id, question, answer, citations_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                question,
                answer,
                json.dumps(citations),
                datetime.utcnow().isoformat(),
            ),
        )


def save_reminder(upload_id: int, message: str, remind_at: str) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders (upload_id, message, remind_at, sent, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (
                upload_id,
                message,
                remind_at,
                datetime.utcnow().isoformat(),
            ),
        )
        return int(cursor.lastrowid)


def get_due_reminders(now_iso: str) -> List[sqlite3.Row]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE sent = 0 AND remind_at <= ?",
            (now_iso,),
        ).fetchall()
    return rows


def mark_reminder_sent(reminder_id: int) -> None:
    with get_db() as conn:
        conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))


def get_stats() -> Tuple[int, int, int]:
    with get_db() as conn:
        uploads = conn.execute("SELECT COUNT(1) AS c FROM uploads").fetchone()["c"]
        chats = conn.execute("SELECT COUNT(1) AS c FROM chat_logs").fetchone()["c"]
        reminders = conn.execute("SELECT COUNT(1) AS c FROM reminders").fetchone()["c"]
    return int(uploads), int(chats), int(reminders)


def save_metric(metric_name: str, metric_value: float, context: str) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO eval_metrics (metric_name, metric_value, context, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (metric_name, metric_value, context, datetime.utcnow().isoformat()),
            )
    except sqlite3.OperationalError:
        init_db()
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO eval_metrics (metric_name, metric_value, context, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (metric_name, metric_value, context, datetime.utcnow().isoformat()),
            )


def get_metric_summary() -> Dict[str, float]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT metric_name, AVG(metric_value) AS avg_value
                FROM eval_metrics
                GROUP BY metric_name
                """
            ).fetchall()
    except sqlite3.OperationalError:
        init_db()
        rows = []
    return {row["metric_name"]: round(float(row["avg_value"]), 3) for row in rows}
