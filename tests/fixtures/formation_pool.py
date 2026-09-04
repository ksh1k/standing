"""Synthetic pools for Phase 3 formation tests (fast-converging bitmaps)."""

from __future__ import annotations

from standing.constants import (
    MEETING_DURATION_SLOTS,
    SLOTS_PER_WEEK,
    CampusZone,
    StudyStyle,
    YearLevel,
    is_legal_meeting_start,
)
from standing.formation.objective import FormationStudent
from standing.models import TimeOfDayWeights
from standing.negotiation.coordinator_negotiate import InProcessMember

# Monday 07:00 — first legal start; uniform ToD → confirms on first propose.
FAST_SLOT: int = 0

YEARS = (
    YearLevel.FRESHMAN,
    YearLevel.SOPHOMORE,
    YearLevel.JUNIOR,
    YearLevel.SENIOR,
    YearLevel.GRAD,
)
ZONES = (
    CampusZone.MAIN_LIBRARY,
    CampusZone.WEST_CAMPUS,
    CampusZone.STUDENT_CENTER,
    CampusZone.EAST_CAMPUS,
    CampusZone.ENGINEERING_QUAD,
)
STYLES = (
    StudyStyle.DISCUSSION,
    StudyStyle.QUIET_PARALLEL,
    StudyStyle.PROBLEM_DRILLING,
)


def free_at(*starts: int) -> str:
    bits = ["0"] * SLOTS_PER_WEEK
    for s in starts:
        if not is_legal_meeting_start(s):
            raise ValueError(s)
        for off in range(MEETING_DURATION_SLOTS):
            bits[s + off] = "1"
    return "".join(bits)


def busy_bitmap() -> str:
    return "0" * SLOTS_PER_WEEK


def make_student(
    sid: str,
    *,
    course: str = "CSCE221",
    year: YearLevel = YearLevel.JUNIOR,
    style: StudyStyle = StudyStyle.DISCUSSION,
    zones: tuple[CampusZone, ...] = (CampusZone.MAIN_LIBRARY,),
    size: int = 4,
) -> FormationStudent:
    return FormationStudent(
        student_id=sid,
        year=year,
        courses=[course],
        preferred_group_size=size,
        preferred_zones=list(zones),
        study_style=style,
    )


def make_member(sid: str, bitmap: str | None = None) -> InProcessMember:
    tod = TimeOfDayWeights(morning=5.0, afternoon=1.0, evening=1.0)
    return InProcessMember(
        student_id=sid,
        _availability=bitmap if bitmap is not None else free_at(FAST_SLOT),
        tod=tod,
    )


def pool_eight_same_course() -> tuple[
    list[FormationStudent], dict[str, InProcessMember]
]:
    """8 students, one course → greedy packs 4+4 (places all); naive packs 6."""
    students: list[FormationStudent] = []
    members: dict[str, InProcessMember] = {}
    for i in range(8):
        sid = f"p{i}"
        students.append(
            make_student(
                sid,
                year=YEARS[i % len(YEARS)],
                style=STYLES[0 if i < 4 else 1],
                zones=(ZONES[i % 2], ZONES[(i + 1) % 2]),
            )
        )
        members[sid] = make_member(sid)
    return students, members


def pool_no_overlap() -> tuple[
    list[FormationStudent], dict[str, InProcessMember]
]:
    """4 students, same course, pairwise-disjoint availability → no CONFIRM."""
    students = [make_student(f"n{i}") for i in range(4)]
    # Distinct non-overlapping windows so no unanimous slot.
    starts = [0, 10, 20, 32]  # different ToD / day
    members = {
        f"n{i}": make_member(f"n{i}", free_at(starts[i])) for i in range(4)
    }
    return students, members


def pool_soft_improvable() -> tuple[
    list[FormationStudent],
    list[tuple[str, str, list[str]]],
    list[str],
    dict[str, FormationStudent],
]:
    """Hand partition with mixed styles; a swap raises style coherence."""
    # Two groups of 4, same course. Intentionally cross-style.
    specs = [
        ("a0", StudyStyle.DISCUSSION, YearLevel.FRESHMAN),
        ("a1", StudyStyle.QUIET_PARALLEL, YearLevel.SOPHOMORE),
        ("a2", StudyStyle.DISCUSSION, YearLevel.JUNIOR),
        ("a3", StudyStyle.QUIET_PARALLEL, YearLevel.SENIOR),
        ("b0", StudyStyle.DISCUSSION, YearLevel.GRAD),
        ("b1", StudyStyle.QUIET_PARALLEL, YearLevel.FRESHMAN),
        ("b2", StudyStyle.DISCUSSION, YearLevel.SOPHOMORE),
        ("b3", StudyStyle.QUIET_PARALLEL, YearLevel.JUNIOR),
    ]
    students = [
        make_student(sid, style=style, year=year) for sid, style, year in specs
    ]
    by_id = {s.student_id: s for s in students}
    # Mixed partition (2 discussion + 2 quiet each) — suboptimal vs pure styles
    groups = [
        ("g0", "CSCE221", ["a0", "a1", "a2", "a3"]),
        ("g1", "CSCE221", ["b0", "b1", "b2", "b3"]),
    ]
    return students, groups, [], by_id
