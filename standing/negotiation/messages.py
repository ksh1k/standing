"""Negotiation message types and verdicts (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class VerdictKind(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    ACCEPT_IF_SHIFTED = "accept_if_shifted"


ALLOWED_SHIFT_DELTAS: frozenset[int] = frozenset({-2, -1, 1, 2})


@dataclass(frozen=True)
class Verdict:
    kind: VerdictKind
    delta: int | None = None

    def __post_init__(self) -> None:
        if self.kind is VerdictKind.ACCEPT_IF_SHIFTED:
            if self.delta not in ALLOWED_SHIFT_DELTAS:
                raise ValueError(f"delta must be in {{-2,-1,+1,+2}}, got {self.delta}")
        elif self.delta is not None:
            raise ValueError("delta only allowed for accept_if_shifted")

    @staticmethod
    def accept() -> Verdict:
        return Verdict(VerdictKind.ACCEPT)

    @staticmethod
    def reject() -> Verdict:
        return Verdict(VerdictKind.REJECT)

    @staticmethod
    def accept_if_shifted(delta: int) -> Verdict:
        return Verdict(VerdictKind.ACCEPT_IF_SHIFTED, delta=delta)

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind.value}
        if self.delta is not None:
            d["delta"] = self.delta
        return d


@dataclass(frozen=True)
class Propose:
    """Coordinator → member: propose a 90-min window start."""

    group_id: str
    start_slot: int
    type: Literal["PROPOSE"] = "PROPOSE"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "group_id": self.group_id,
            "start_slot": self.start_slot,
        }


@dataclass(frozen=True)
class Respond:
    """Member → coordinator: verdict for a proposed slot.

    student_id is NOT part of the wire message (leakage); callers may track
    identity ephemerally in memory only.
    """

    group_id: str
    start_slot: int
    verdict: Verdict
    type: Literal["RESPOND"] = "RESPOND"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "group_id": self.group_id,
            "start_slot": self.start_slot,
            "verdict": self.verdict.as_dict(),
        }


@dataclass(frozen=True)
class Confirm:
    """Coordinator → all members: unanimous slot locked."""

    group_id: str
    start_slot: int
    type: Literal["CONFIRM"] = "CONFIRM"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "group_id": self.group_id,
            "start_slot": self.start_slot,
        }


@dataclass(frozen=True)
class Withdraw:
    """Member → coordinator: leave the negotiation."""

    group_id: str
    reason: str
    student_id: str | None = None
    type: Literal["WITHDRAW"] = "WITHDRAW"

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type,
            "group_id": self.group_id,
            "reason": self.reason,
        }
        if self.student_id is not None:
            d["student_id"] = self.student_id
        return d
