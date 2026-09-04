"""Slot-grid and campus-zone constants (224 slots/week; 210 legal 90-min starts)."""

from __future__ import annotations

from enum import Enum
from typing import Final

DAYS_PER_WEEK: Final[int] = 7
SLOTS_PER_DAY: Final[int] = 32  # 07:00–23:00 inclusive start, 30-min
SLOTS_PER_WEEK: Final[int] = DAYS_PER_WEEK * SLOTS_PER_DAY  # 224
MEETING_DURATION_SLOTS: Final[int] = 3  # 90 minutes
LEGAL_STARTS_PER_DAY: Final[int] = SLOTS_PER_DAY - MEETING_DURATION_SLOTS + 1  # 30
LEGAL_STARTS_PER_WEEK: Final[int] = LEGAL_STARTS_PER_DAY * DAYS_PER_WEEK  # 210

DAY_NAMES: Final[tuple[str, ...]] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

GRID_START_HOUR: Final[int] = 7
GRID_END_HOUR: Final[int] = 23  # exclusive end for last slot start at 22:30
SLOT_MINUTES: Final[int] = 30

DEFAULT_GROUP_SIZE_MIN: Final[int] = 4
DEFAULT_GROUP_SIZE_MAX: Final[int] = 6


class YearLevel(str, Enum):
    FRESHMAN = "freshman"
    SOPHOMORE = "sophomore"
    JUNIOR = "junior"
    SENIOR = "senior"
    GRAD = "grad"


class StudyStyle(str, Enum):
    QUIET_PARALLEL = "quiet_parallel"
    DISCUSSION = "discussion"
    PROBLEM_DRILLING = "problem_drilling"


class CampusZone(str, Enum):
    """Public campus zones only — never residential."""

    WEST_CAMPUS = "west_campus"
    EAST_CAMPUS = "east_campus"
    MAIN_LIBRARY = "main_library"
    STUDENT_CENTER = "student_center"
    ENGINEERING_QUAD = "engineering_quad"


class GroupStatus(str, Enum):
    FORMING = "forming"
    ACTIVE = "active"
    DISBANDED = "disbanded"


class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


def slot_index(day: int, slot_in_day: int) -> int:
    """(day 0–6, slot-in-day 0–31) → week index 0–223."""
    if not 0 <= day < DAYS_PER_WEEK:
        raise ValueError(f"day must be 0..{DAYS_PER_WEEK - 1}, got {day}")
    if not 0 <= slot_in_day < SLOTS_PER_DAY:
        raise ValueError(f"slot_in_day must be 0..{SLOTS_PER_DAY - 1}, got {slot_in_day}")
    return day * SLOTS_PER_DAY + slot_in_day


def is_legal_meeting_start(index: int) -> bool:
    """Valid start for a 3-slot meeting (no day-boundary cross)."""
    if not 0 <= index < SLOTS_PER_WEEK:
        return False
    slot_in_day = index % SLOTS_PER_DAY
    return slot_in_day <= SLOTS_PER_DAY - MEETING_DURATION_SLOTS
