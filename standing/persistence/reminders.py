"""Weekly reminder: 24h before each session, member notifies its own student."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from standing.db import connect
from standing.persistence.clock import parse_iso, to_iso

REMINDER_LEAD = timedelta(hours=24)
KIND = "reminder"


@dataclass(frozen=True)
class ReminderResult:
    session_id: str
    student_id: str
    body: str
    created: bool


def _already_sent(conn, student_id: str, session_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM notifications WHERE student_id=? AND kind=? AND session_id=?",
        (student_id, KIND, session_id),
    ).fetchone()
    return row is not None


def reminder_due(session_dt: datetime, now: datetime) -> bool:
    """True when now is at/after session-24h and before the session (not earlier)."""
    window_start = session_dt - REMINDER_LEAD
    return window_start <= now < session_dt


def check_reminders(
    member_db: str | Path,
    student_id: str,
    now: datetime,
) -> list[ReminderResult]:
    """Scan local_sessions; insert reminder notifications when due."""
    results: list[ReminderResult] = []
    with connect(member_db) as conn:
        sessions = conn.execute(
            "SELECT session_id, scheduled_datetime, location FROM local_sessions"
        ).fetchall()
        for row in sessions:
            sid = row["session_id"]
            session_dt = parse_iso(row["scheduled_datetime"])
            if not reminder_due(session_dt, now):
                continue
            if _already_sent(conn, student_id, sid):
                results.append(
                    ReminderResult(sid, student_id, "", created=False)
                )
                continue
            body = (
                f"Study session reminder: {row['scheduled_datetime']} "
                f"at {row['location']}"
            )
            conn.execute(
                """
                INSERT INTO notifications (student_id, kind, body, session_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, KIND, body, sid, to_iso(now)),
            )
            results.append(ReminderResult(sid, student_id, body, created=True))
        conn.commit()
    return results
