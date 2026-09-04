"""Drift: aggregate attendance <50% for 3 consecutive sessions → renegotiate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from standing.db import connect
from standing.persistence.clock import to_iso

DRIFT_RATIO = 0.5
DRIFT_STREAK = 3

RenegotiateFn = Callable[[str], object]  # group_id -> NegotiationResult-like


@dataclass(frozen=True)
class DriftResult:
    group_id: str
    triggered: bool
    consecutive_low: int
    new_slot: int | None
    status: str  # ok | triggered | renegotiated | failed


def session_low(attended_count: int, member_total: int) -> bool:
    if member_total <= 0:
        return False
    return (attended_count / member_total) < DRIFT_RATIO


def consecutive_low_streak(
    aggregates: list[tuple[int, int]],
) -> int:
    """Trailing count of sessions with attendance ratio < 50%."""
    n = 0
    for attended, total in reversed(aggregates):
        if session_low(attended, total):
            n += 1
        else:
            break
    return n


def load_group_aggregates(coord_db: str | Path, group_id: str) -> list[tuple[str, int, int]]:
    """Chronological (session_id, attended_count, member_total) for group."""
    with connect(coord_db) as conn:
        rows = conn.execute(
            """
            SELECT s.session_id, a.attended_count, a.member_total
            FROM sessions s
            JOIN session_aggregates a ON a.session_id = s.session_id
            LEFT JOIN session_kinds k ON k.session_id = s.session_id
            WHERE s.group_id = ?
              AND COALESCE(k.kind, 'regular') = 'regular'
            ORDER BY s.scheduled_datetime ASC
            """,
            (group_id,),
        ).fetchall()
    return [(r["session_id"], int(r["attended_count"]), int(r["member_total"])) for r in rows]


def check_drift(
    coord_db: str | Path,
    group_id: str,
    now: datetime,
    renegotiate: RenegotiateFn | None = None,
) -> DriftResult:
    """Trigger Phase-2 renegotiation when 3 consecutive regular sessions are low."""
    rows = load_group_aggregates(coord_db, group_id)
    pairs = [(a, t) for _, a, t in rows]
    streak = consecutive_low_streak(pairs)
    if streak < DRIFT_STREAK:
        return DriftResult(group_id, False, streak, None, "ok")

    new_slot: int | None = None
    status = "triggered"
    if renegotiate is not None:
        result = renegotiate(group_id)
        slot = getattr(result, "start_slot", None)
        rstatus = getattr(result, "status", None)
        if rstatus == "confirmed" and slot is not None:
            new_slot = int(slot)
            status = "renegotiated"
            with connect(coord_db) as conn:
                conn.execute(
                    "UPDATE groups SET scheduled_slot=? WHERE group_id=?",
                    (new_slot, group_id),
                )
                conn.commit()
        else:
            status = "failed"

    with connect(coord_db) as conn:
        conn.execute(
            """
            INSERT INTO drift_events
                (group_id, triggered_at, consecutive_low, new_slot, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, to_iso(now), streak, new_slot, status),
        )
        conn.commit()

    return DriftResult(group_id, True, streak, new_slot, status)
