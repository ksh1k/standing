"""Formation objective: W_PLACE ≫ W_STYLE ≫ W_YEAR ≫ W_ZONE (see DECISIONS)."""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

from standing.constants import CampusZone, StudyStyle, YearLevel

W_PLACE: float = 1_000_000.0
W_STYLE: float = 1_000.0
W_YEAR: float = 10.0
W_ZONE: float = 1.0


class FormationStudent:
    """Coordinator pool view for soft scoring (no availability)."""

    __slots__ = (
        "student_id",
        "year",
        "courses",
        "preferred_group_size",
        "preferred_zones",
        "study_style",
    )

    def __init__(
        self,
        student_id: str,
        year: YearLevel,
        courses: Sequence[str],
        preferred_group_size: int,
        preferred_zones: Sequence[CampusZone],
        study_style: StudyStyle,
    ) -> None:
        self.student_id = student_id
        self.year = year
        self.courses = list(courses)
        self.preferred_group_size = preferred_group_size
        self.preferred_zones = frozenset(preferred_zones)
        self.study_style = study_style


def style_coherence(members: Sequence[FormationStudent]) -> float:
    """Modal study_style fraction (0..1)."""
    if not members:
        return 0.0
    counts = Counter(m.study_style for m in members)
    return counts.most_common(1)[0][1] / len(members)


def year_diversity(members: Sequence[FormationStudent]) -> float:
    """Unique years / size (0..1)."""
    if not members:
        return 0.0
    return len({m.year for m in members}) / len(members)


def zone_overlap(members: Sequence[FormationStudent]) -> float:
    """Mean pairwise Jaccard of preferred_zones (0..1)."""
    n = len(members)
    if n < 2:
        return 1.0 if n == 1 and members[0].preferred_zones else 0.0
    total = 0.0
    pairs = 0
    for i in range(n):
        zi = members[i].preferred_zones
        for j in range(i + 1, n):
            zj = members[j].preferred_zones
            union = zi | zj
            if not union:
                sim = 0.0
            else:
                sim = len(zi & zj) / len(union)
            total += sim
            pairs += 1
    return total / pairs if pairs else 0.0


def group_soft_score(members: Sequence[FormationStudent]) -> float:
    return (
        W_STYLE * style_coherence(members)
        + W_YEAR * year_diversity(members)
        + W_ZONE * zone_overlap(members)
    )


def partition_score(
    groups: Sequence[Sequence[str]],
    students: Mapping[str, FormationStudent],
) -> float:
    """Score partition of member-id lists (unplaced = 0)."""
    placed = sum(len(g) for g in groups)
    soft = 0.0
    for g in groups:
        members = [students[sid] for sid in g]
        soft += group_soft_score(members)
    return W_PLACE * placed + soft
