"""5-student fixture with a unique unanimous slot (default Wed 14:00 = 78).

Tests use EXPECTED_UNANIMOUS_SLOT=78. Demo can pass a random legal start.
All five free only on [target, target+1, target+2]. Afternoon decoys before
the target (when available) are free for 4/5 so search must walk them.
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


def build_five_student_bitmaps(unanimous_slot: int | None = None) -> dict[str, str]:
    target = EXPECTED_UNANIMOUS_SLOT if unanimous_slot is None else int(unanimous_slot)
    if not is_legal_meeting_start(target):
        raise ValueError(f"not a legal start: {target}")

    bits_map = {sid: _empty_busy() for sid in STUDENT_IDS}
    for sid in STUDENT_IDS:
        _free_window(bits_map[sid], target)

    # Prefer afternoon decoys before target; fall back to any non-overlapping legal starts.
    raw = [
        s
        for s in all_legal_starts()
        if time_of_day_for_slot(s) is TimeOfDay.AFTERNOON
        and s < target
        and not _windows_overlap(s, target)
    ]
    if len(raw) < 3:
        raw = [
            s
            for s in all_legal_starts()
            if s != target and not _windows_overlap(s, target)
        ]

    decoys: list[int] = []
    for s in raw:
        if any(_windows_overlap(s, d) for d in decoys):
            continue
        decoys.append(s)
        if len(decoys) >= 12:
            break

    for i, start in enumerate(decoys):
        busy_member = STUDENT_IDS[i % len(STUDENT_IDS)]
        for sid in STUDENT_IDS:
            if sid != busy_member:
                _free_window(bits_map[sid], start)

    bitmaps = {sid: "".join(bits) for sid, bits in bits_map.items()}
    for start in all_legal_starts():
        n_free = sum(1 for sid in STUDENT_IDS if window_free(bitmaps[sid], start))
        if start == target:
            assert n_free == 5, (start, n_free)
        else:
            assert n_free < 5, (start, n_free)
    return bitmaps


def build_five_members(unanimous_slot: int | None = None):
    from standing.negotiation.coordinator_negotiate import InProcessMember

    bitmaps = build_five_student_bitmaps(unanimous_slot=unanimous_slot)
    return [
        InProcessMember(student_id=sid, _availability=bitmaps[sid], tod=GROUP_TOD)
        for sid in STUDENT_IDS
    ]
