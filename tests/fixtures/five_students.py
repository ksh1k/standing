"""5-student fixture: unique unanimous slot EXPECTED_UNANIMOUS_SLOT=78 (Wed 14:00).

All five free only on [78,79,80]. Afternoon decoys before 78 free for 4/5 so search
must walk them (not first-pick). High afternoon ToD weight prefers those candidates.
"""

from __future__ import annotations

from standing.constants import (
    MEETING_DURATION_SLOTS,
    SLOTS_PER_WEEK,
    TimeOfDay,
    is_legal_meeting_start,
)
from standing.models import TimeOfDayWeights
from standing.negotiation.member_eval import window_free
from standing.negotiation.search import all_legal_starts, time_of_day_for_slot

EXPECTED_UNANIMOUS_SLOT: int = 78
STUDENT_IDS: tuple[str, ...] = ("s0", "s1", "s2", "s3", "s4")
GROUP_TOD = TimeOfDayWeights(morning=0.5, afternoon=5.0, evening=0.5)


def _empty_busy() -> list[str]:
    return ["0"] * SLOTS_PER_WEEK


def _free_window(bits: list[str], start: int) -> None:
    if not is_legal_meeting_start(start):
        raise ValueError(f"not a legal start: {start}")
    for off in range(MEETING_DURATION_SLOTS):
        bits[start + off] = "1"


def _windows_overlap(a: int, b: int) -> bool:
    return not (
        a + MEETING_DURATION_SLOTS - 1 < b or b + MEETING_DURATION_SLOTS - 1 < a
    )


def build_five_student_bitmaps() -> dict[str, str]:
    bits_map = {sid: _empty_busy() for sid in STUDENT_IDS}
    for sid in STUDENT_IDS:
        _free_window(bits_map[sid], EXPECTED_UNANIMOUS_SLOT)

    raw = [
        s
        for s in all_legal_starts()
        if time_of_day_for_slot(s) is TimeOfDay.AFTERNOON
        and s < EXPECTED_UNANIMOUS_SLOT
        and not _windows_overlap(s, EXPECTED_UNANIMOUS_SLOT)
    ]
    decoys: list[int] = []
    for s in raw:
        if any(_windows_overlap(s, d) for d in decoys):
            continue
        decoys.append(s)

    for i, start in enumerate(decoys):
        busy_member = STUDENT_IDS[i % len(STUDENT_IDS)]
        for sid in STUDENT_IDS:
            if sid != busy_member:
                _free_window(bits_map[sid], start)

    bitmaps = {sid: "".join(bits) for sid, bits in bits_map.items()}
    for start in all_legal_starts():
        n_free = sum(1 for sid in STUDENT_IDS if window_free(bitmaps[sid], start))
        if start == EXPECTED_UNANIMOUS_SLOT:
            assert n_free == 5, (start, n_free)
        else:
            assert n_free < 5, (start, n_free)
    return bitmaps


def build_five_members():
    from standing.negotiation.coordinator_negotiate import InProcessMember

    bitmaps = build_five_student_bitmaps()
    return [
        InProcessMember(student_id=sid, _availability=bitmaps[sid], tod=GROUP_TOD)
        for sid in STUDENT_IDS
    ]
