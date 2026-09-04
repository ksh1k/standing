"""Pydantic / dataclass shapes for Phase 1 (no business logic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from standing.constants import (
    CampusZone,
    StudyStyle,
    TimeOfDay,
    YearLevel,
)


@dataclass
class TimeOfDayWeights:
    """Relative preference weights for morning / afternoon / evening."""

    morning: float = 1.0
    afternoon: float = 1.0
    evening: float = 1.0

    def as_dict(self) -> dict[str, float]:
        return {
            TimeOfDay.MORNING.value: self.morning,
            TimeOfDay.AFTERNOON.value: self.afternoon,
            TimeOfDay.EVENING.value: self.evening,
        }


@dataclass
class MemberProfile:
    """Full student profile — lives ONLY in the member agent DB.

    Availability bitmap (224 bits) must never leave the member store.
    """

    student_id: str
    display_name: str
    year: YearLevel
    courses: list[str]
    availability: str  # 224-char '0'/'1' bitmap or compact encoding
    preferred_group_size: int
    preferred_zones: list[CampusZone]
    study_style: StudyStyle
    time_of_day_preference: TimeOfDayWeights = field(default_factory=TimeOfDayWeights)


@dataclass
class CoordinatorStudentView:
    """Coordinator-visible student fields — NEVER includes availability."""

    student_id: str
    year: YearLevel
    courses: list[str]
    preferred_group_size: int
    preferred_zones: list[CampusZone]
    study_style: StudyStyle


def normalize_course_code(raw: str) -> str:
    """Normalize course codes: uppercase, strip whitespace."""
    return "".join(raw.split()).upper()


def profile_to_dict(profile: MemberProfile) -> dict[str, Any]:
    """Serialize member profile for storage helpers (no I/O)."""
    return {
        "student_id": profile.student_id,
        "display_name": profile.display_name,
        "year": profile.year.value,
        "courses": [normalize_course_code(c) for c in profile.courses],
        "availability": profile.availability,
        "preferred_group_size": profile.preferred_group_size,
        "preferred_zones": [z.value for z in profile.preferred_zones],
        "study_style": profile.study_style.value,
        "time_of_day_preference": profile.time_of_day_preference.as_dict(),
    }
