"""Course wait-pool join + Phase-3 match (availability stays in member DB)."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from standing.constants import CampusZone, StudyStyle, YearLevel
from standing.db import connect
from standing.formation.objective import FormationStudent
from standing.formation.pipeline import form_groups
from standing.models import TimeOfDayWeights, normalize_course_code
from standing.negotiation.coordinator_negotiate import InProcessMember

POOL_MATCH_MIN = 4


def _zones(raw: str) -> list[CampusZone]:
    out: list[CampusZone] = []
    for z in json.loads(raw or "[]"):
        try:
            out.append(CampusZone(z))
        except ValueError:
            continue
    return out


def _pick_zone(students: list[FormationStudent]) -> str:
    counts: Counter[str] = Counter()
    for s in students:
        for z in s.preferred_zones:
            counts[z.value] += 1
    if counts:
        return counts.most_common(1)[0][0]
    return CampusZone.MAIN_LIBRARY.value


def load_pool_formation(
    *,
    coord_db: Path,
    member_db: Path,
    course_code: str,
) -> tuple[list[FormationStudent], dict[str, InProcessMember], dict[str, TimeOfDayWeights]]:
    """Build formation inputs for waiting students (bitmaps from member only)."""
    course = normalize_course_code(course_code)
    pool: list[FormationStudent] = []
    members: dict[str, InProcessMember] = {}
    tods: dict[str, TimeOfDayWeights] = {}

    with connect(coord_db) as cconn, connect(member_db) as mconn:
        rows = cconn.execute(
            "SELECT student_id FROM course_pool WHERE course_code = ? AND status = 'waiting'",
            (course,),
        ).fetchall()
        for r in rows:
            sid = r["student_id"]
            crow = cconn.execute(
                "SELECT * FROM students WHERE student_id = ?", (sid,)
            ).fetchone()
            mrow = mconn.execute(
                "SELECT availability, time_of_day_preference FROM student_profile "
                "WHERE student_id = ?",
                (sid,),
            ).fetchone()
            if crow is None or mrow is None:
                continue
            courses = json.loads(crow["courses"] or "[]")
            if course not in courses:
                continue
            fs = FormationStudent(
                student_id=sid,
                year=YearLevel(crow["year"]),
                courses=courses,
                preferred_group_size=int(crow["preferred_group_size"]),
                preferred_zones=_zones(crow["preferred_zones"]),
                study_style=StudyStyle(crow["study_style"]),
            )
            pool.append(fs)
            tod_raw = json.loads(mrow["time_of_day_preference"] or "{}")
            tod = TimeOfDayWeights(
                morning=float(tod_raw.get("morning", 1.0)),
                afternoon=float(tod_raw.get("afternoon", 1.0)),
                evening=float(tod_raw.get("evening", 1.0)),
            )
            tods[sid] = tod
            members[sid] = InProcessMember(
                student_id=sid,
                _availability=mrow["availability"],
                tod=tod,
            )
    return pool, members, tods


def run_course_match(
    *,
    coord_db: Path,
    member_db: Path,
    course_code: str,
    persist_confirmed,
    log_dir: Path | None = None,
) -> dict[str, Any]:
    """Run Phase 3 on a course wait pool; persist CONFIRM groups; mark matched."""
    course = normalize_course_code(course_code)
    pool, members, tods = load_pool_formation(
        coord_db=coord_db, member_db=member_db, course_code=course
    )
    if len(pool) < POOL_MATCH_MIN:
        return {
            "status": "too_small",
            "course_code": course,
            "pool_size": len(pool),
            "min_required": POOL_MATCH_MIN,
            "groups": [],
        }

    result = form_groups(pool, members, tods, log_dir=log_dir)
    confirmed: list[dict[str, Any]] = []
    matched_ids: set[str] = set()

    by_id = {s.student_id: s for s in pool}
    for g in result.groups:
        member_list = list(g.member_ids)
        zone = _pick_zone([by_id[sid] for sid in member_list if sid in by_id])
        gid = f"g-{uuid.uuid4().hex[:12]}"
        session_id = persist_confirmed(
            group_id=gid,
            course_code=course,
            member_ids=member_list,
            start_slot=g.confirmed_slot,
            zone=zone,
        )
        confirmed.append(
            {
                "group_id": gid,
                "course_code": course,
                "member_ids": member_list,
                "scheduled_slot": g.confirmed_slot,
                "zone": zone,
                "session_id": session_id,
            }
        )
        matched_ids.update(member_list)

    if matched_ids:
        with connect(coord_db) as conn:
            for sid in matched_ids:
                conn.execute(
                    "UPDATE course_pool SET status = 'matched' "
                    "WHERE course_code = ? AND student_id = ? AND status = 'waiting'",
                    (course, sid),
                )
            conn.commit()

    return {
        "status": "ok" if confirmed else "no_confirm",
        "course_code": course,
        "pool_size": len(pool),
        "groups": confirmed,
        "unplaced": result.unplaced,
        "rejected_candidates": result.rejected_candidates,
    }
