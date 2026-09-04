"""Candidate generation and time-of-day scoring for negotiation search."""

from __future__ import annotations

from standing.constants import (
    LEGAL_STARTS_PER_WEEK,
    SLOTS_PER_DAY,
    TimeOfDay,
    is_legal_meeting_start,
)
from standing.models import TimeOfDayWeights

# Slot-in-day → ToD bucket (07:00–23:00 grid, 30-min slots).
# morning: 07:00–11:30 (0–9), afternoon: 12:00–16:30 (10–19), evening: 17:00–22:30 (20–29)
_MORNING_END = 10
_AFTERNOON_END = 20

SHIFT_HINT_BONUS: float = 1.0


def all_legal_starts() -> list[int]:
    """All 210 legal meeting start indices in week-bitmap coordinates."""
    starts = [i for i in range(7 * SLOTS_PER_DAY) if is_legal_meeting_start(i)]
    assert len(starts) == LEGAL_STARTS_PER_WEEK
    return starts


def time_of_day_for_slot(start_slot: int) -> TimeOfDay:
    slot_in_day = start_slot % SLOTS_PER_DAY
    if slot_in_day < _MORNING_END:
        return TimeOfDay.MORNING
    if slot_in_day < _AFTERNOON_END:
        return TimeOfDay.AFTERNOON
    return TimeOfDay.EVENING


def weight_for_slot(weights: TimeOfDayWeights, start_slot: int) -> float:
    tod = time_of_day_for_slot(start_slot)
    if tod is TimeOfDay.MORNING:
        return weights.morning
    if tod is TimeOfDay.AFTERNOON:
        return weights.afternoon
    return weights.evening


def aggregate_score(
    start_slot: int,
    member_weights: list[TimeOfDayWeights],
    shift_bonus: float = 0.0,
) -> float:
    """Mean ToD preference across members plus optional shift-hint bonus."""
    if not member_weights:
        base = 0.0
    else:
        base = sum(weight_for_slot(w, start_slot) for w in member_weights) / len(
            member_weights
        )
    return base + shift_bonus
