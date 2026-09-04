"""Dormancy: after 3 consecutive misses, private low-pressure check-in only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from standing.db import connect
from standing.persistence.clock import to_iso

CONSECUTIVE_MISSES = 3
KIND = "dormancy_checkin"
CHECKIN_BODY = (
    "We've missed you at the last few study sessions. "
    "No pressure — just checking in if you'd like to rejoin when you're ready."
)


@dataclass(frozen=True)
class DormancyResult:
    student_id: str
    consecutive_misses: int
    notified: bool
    private: bool = True


def consecutive_miss_count(attended_flags: list[int]) -> int:
    """Count trailing consecutive misses (0) in chronological order."""
    n = 0
    for flag in reversed(attended_flags):
        if flag == 0:
            n += 1
        else:
            break
    return n


def is_dormant(attended_flags: list[int]) -> bool:
    return consecutive_miss_count(attended_flags) >= CONSECUTIVE_MISSES


def _ordered_attendance(conn, student_id: str) -> list[tuple[str, int]]:
    rows = conn.execute(
        """
        SELECT a.session_id, a.attended
        FROM attendance a
        JOIN local_sessions ls ON ls.session_id = a.session_id
        WHERE a.student_id = ?
        ORDER BY ls.scheduled_datetime ASC
        """,
        (student_id,),
    ).fetchall()
    return [(r["session_id"], int(r["attended"])) for r in rows]


def _already_notified(conn, student_id: str, anchor_session_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM notifications WHERE student_id=? AND kind=? AND session_id=?",
        (student_id, KIND, anchor_session_id),
    ).fetchone()
    return row is not None


def check_dormancy(
    member_db: str | Path,
    student_id: str,
    now: datetime,
) -> DormancyResult:
    """If last 3 sessions missed, insert a private dormancy notification once."""
    with connect(member_db) as conn:
        records = _ordered_attendance(conn, student_id)
        flags = [attended for _, attended in records]
        misses = consecutive_miss_count(flags)
        if misses < CONSECUTIVE_MISSES:
            return DormancyResult(student_id, misses, notified=False)
        # Anchor on the third consecutive miss (last of the trailing streak start+2)
        anchor = records[-1][0]
        if _already_notified(conn, student_id, anchor):
            return DormancyResult(student_id, misses, notified=False)
        conn.execute(
            """
            INSERT INTO notifications (student_id, kind, body, session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_id, KIND, CHECKIN_BODY, anchor, to_iso(now)),
        )
        conn.commit()
        return DormancyResult(student_id, misses, notified=True, private=True)
