"""Exam season: second weekly session in the two weeks before an exam; revert after."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from standing.db import connect
from standing.persistence.clock import parse_iso, to_iso

EXAM_WINDOW_DAYS = 14
SECOND_SESSION_OFFSET = timedelta(days=3)


@dataclass(frozen=True)
class ExamAdaptResult:
    group_id: str
    in_window: bool
    added_session_id: str | None
    removed_session_ids: list[str]


def parse_exam_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def in_exam_window(exam_day: date, now: datetime) -> bool:
    """True for now.date() in [exam_day - 14d, exam_day)."""
    today = now.astimezone().date() if now.tzinfo else now.date()
    start = exam_day - timedelta(days=EXAM_WINDOW_DAYS)
    return start <= today < exam_day


def course_in_window(coord_db: str | Path, course_code: str, now: datetime) -> bool:
    with connect(coord_db) as conn:
        rows = conn.execute(
            "SELECT exam_date FROM exam_dates WHERE course_code=?",
            (course_code,),
        ).fetchall()
    return any(in_exam_window(parse_exam_date(r["exam_date"]), now) for r in rows)


def _exam_season_sessions(conn, group_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT s.session_id
        FROM sessions s
        JOIN session_kinds k ON k.session_id = s.session_id
        WHERE s.group_id=? AND k.kind='exam_season'
        """,
        (group_id,),
    ).fetchall()
    return [r["session_id"] for r in rows]


def _primary_session(conn, group_id: str) -> tuple[str, str, str] | None:
    row = conn.execute(
        """
        SELECT s.session_id, s.scheduled_datetime, s.location
        FROM sessions s
        LEFT JOIN session_kinds k ON k.session_id = s.session_id
        WHERE s.group_id=?
          AND COALESCE(k.kind, 'regular') = 'regular'
        ORDER BY s.scheduled_datetime ASC
        LIMIT 1
        """,
        (group_id,),
    ).fetchone()
    if row is None:
        return None
    return row["session_id"], row["scheduled_datetime"], row["location"]


def adapt_exam_season(
    coord_db: str | Path,
    group_id: str,
    now: datetime,
) -> ExamAdaptResult:
    """Add second weekly session while in exam window; remove after."""
    with connect(coord_db) as conn:
        group = conn.execute(
            "SELECT course_code, zone FROM groups WHERE group_id=?",
            (group_id,),
        ).fetchone()
        if group is None:
            raise ValueError(f"unknown group {group_id}")
        course = group["course_code"]
        window = course_in_window(coord_db, course, now)
        existing = _exam_season_sessions(conn, group_id)

        if window:
            if existing:
                return ExamAdaptResult(group_id, True, None, [])
            primary = _primary_session(conn, group_id)
            if primary is None:
                return ExamAdaptResult(group_id, True, None, [])
            _, primary_dt, location = primary
            second_dt = parse_iso(primary_dt) + SECOND_SESSION_OFFSET
            # Keep second session inside the exam window if possible
            new_id = f"exam-{uuid.uuid4().hex[:12]}"
            loc = location or group["zone"] or "main_library"
            conn.execute(
                """
                INSERT INTO sessions (session_id, group_id, scheduled_datetime, location)
                VALUES (?, ?, ?, ?)
                """,
                (new_id, group_id, to_iso(second_dt), loc),
            )
            conn.execute(
                "INSERT INTO session_kinds (session_id, kind) VALUES (?, 'exam_season')",
                (new_id,),
            )
            conn.commit()
            return ExamAdaptResult(group_id, True, new_id, [])

        removed: list[str] = []
        for sid in existing:
            conn.execute("DELETE FROM session_kinds WHERE session_id=?", (sid,))
            conn.execute("DELETE FROM session_aggregates WHERE session_id=?", (sid,))
            conn.execute("DELETE FROM sessions WHERE session_id=?", (sid,))
            removed.append(sid)
        conn.commit()
        return ExamAdaptResult(group_id, False, None, removed)
