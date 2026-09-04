"""Scheduled persistence checks with an injectible clock."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from standing.persistence.dormancy import check_dormancy
from standing.persistence.drift import RenegotiateFn, check_drift
from standing.persistence.exam_season import adapt_exam_season
from standing.persistence.reminders import check_reminders
from standing.persistence.repair import check_repair


@dataclass
class PersistenceRunner:
    """Run all Phase-5 checks for one tick of `now`."""

    coord_db: str | Path
    member_dbs: dict[str, str | Path]  # student_id -> member db
    group_ids: list[str] = field(default_factory=list)
    # group_id -> active member count (caller supplies; uses dormancy definition)
    active_counts: dict[str, int] = field(default_factory=dict)
    renegotiate: RenegotiateFn | None = None

    def run_member_checks(self, student_id: str, now: datetime) -> dict:
        db = self.member_dbs[student_id]
        return {
            "reminders": check_reminders(db, student_id, now),
            "dormancy": check_dormancy(db, student_id, now),
        }

    def run_group_checks(self, group_id: str, now: datetime) -> dict:
        return {
            "drift": check_drift(
                self.coord_db, group_id, now, renegotiate=self.renegotiate
            ),
            "exam_season": adapt_exam_season(self.coord_db, group_id, now),
            "repair": check_repair(
                self.coord_db,
                group_id,
                self.active_counts.get(group_id, 0),
                now,
            ),
        }

    def tick(self, now: datetime) -> dict:
        member_out = {
            sid: self.run_member_checks(sid, now) for sid in self.member_dbs
        }
        group_out = {
            gid: self.run_group_checks(gid, now) for gid in self.group_ids
        }
        return {"members": member_out, "groups": group_out}
