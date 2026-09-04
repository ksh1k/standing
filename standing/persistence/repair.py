"""Membership repair: flag groups with fewer than 4 active members for merge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from standing.db import connect
from standing.persistence.clock import to_iso
from standing.persistence.dormancy import is_dormant

MIN_ACTIVE_MEMBERS = 4
REASON = "active_members_below_minimum"


@dataclass(frozen=True)
class RepairResult:
    group_id: str
    course_code: str
    active_member_count: int
    flagged: bool


def count_active_from_flags(member_attendance: dict[str, list[int]]) -> int:
    """Active = not dormant (fewer than 3 consecutive trailing misses)."""
    return sum(1 for flags in member_attendance.values() if not is_dormant(flags))


def check_repair(
    coord_db: str | Path,
    group_id: str,
    active_member_count: int,
    now: datetime,
) -> RepairResult:
    """Flag group for course-level merge when active members < 4 (flag only)."""
    with connect(coord_db) as conn:
        group = conn.execute(
            "SELECT course_code FROM groups WHERE group_id=?",
            (group_id,),
        ).fetchone()
        if group is None:
            raise ValueError(f"unknown group {group_id}")
        course = group["course_code"]
        if active_member_count >= MIN_ACTIVE_MEMBERS:
            return RepairResult(group_id, course, active_member_count, flagged=False)

        existing = conn.execute(
            "SELECT flag_id FROM merge_flags WHERE group_id=?",
            (group_id,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO merge_flags
                    (group_id, course_code, active_member_count, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group_id, course, active_member_count, REASON, to_iso(now)),
            )
            conn.commit()
        else:
            conn.execute(
                """
                UPDATE merge_flags
                SET active_member_count=?, reason=?, created_at=?
                WHERE group_id=?
                """,
                (active_member_count, REASON, to_iso(now), group_id),
            )
            conn.commit()
        return RepairResult(group_id, course, active_member_count, flagged=True)
