"""Phase 3 group formation: greedy seed + local search + negotiation gate."""

from standing.formation.pipeline import FormationResult, FormedGroup, form_groups
from standing.formation.objective import (
    W_PLACE,
    W_STYLE,
    W_YEAR,
    W_ZONE,
    partition_score,
)

__all__ = [
    "FormationResult",
    "FormedGroup",
    "form_groups",
    "W_PLACE",
    "W_STYLE",
    "W_YEAR",
    "W_ZONE",
    "partition_score",
]
