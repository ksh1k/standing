"""Pure member-side evaluation of a proposed meeting start against a private bitmap."""

from __future__ import annotations

from standing.constants import MEETING_DURATION_SLOTS, SLOTS_PER_WEEK, is_legal_meeting_start
from standing.negotiation.messages import ALLOWED_SHIFT_DELTAS, Verdict

# Prefer nearer shifts first when offering accept_if_shifted.
_SHIFT_TRY_ORDER: tuple[int, ...] = (-1, 1, -2, 2)


def window_free(availability_bitmap: str, start_slot: int) -> bool:
    """True iff start_slot is legal and all three meeting slots are free ('1')."""
    if len(availability_bitmap) != SLOTS_PER_WEEK:
        raise ValueError(
            f"availability_bitmap must be length {SLOTS_PER_WEEK}, "
            f"got {len(availability_bitmap)}"
        )
    if not is_legal_meeting_start(start_slot):
        return False
    for offset in range(MEETING_DURATION_SLOTS):
        if availability_bitmap[start_slot + offset] != "1":
            return False
    return True


def evaluate(start_slot: int, availability_bitmap: str) -> Verdict:
    """Evaluate a proposed start against the member's private bitmap.

    Returns accept if the 90-min window is free; otherwise accept_if_shifted(delta)
    for the nearest free legal shift in {{-2,-1,+1,+2}}; otherwise reject.
    """
    if window_free(availability_bitmap, start_slot):
        return Verdict.accept()
    for delta in _SHIFT_TRY_ORDER:
        assert delta in ALLOWED_SHIFT_DELTAS
        if window_free(availability_bitmap, start_slot + delta):
            return Verdict.accept_if_shifted(delta)
    return Verdict.reject()
