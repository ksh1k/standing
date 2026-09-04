"""Coordinator negotiation session: propose / aggregate / confirm with leakage-safe state."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from standing.db import connect
from standing.models import TimeOfDayWeights
from standing.negotiation.log import NegotiationLog
from standing.negotiation.messages import (
    Confirm,
    Propose,
    Respond,
    Verdict,
    VerdictKind,
)
from standing.negotiation.search import (
    SHIFT_HINT_BONUS,
    aggregate_score,
    all_legal_starts,
)

PROPOSAL_BUDGET: int = 40

EvaluateFn = Callable[[int], Verdict]


class MemberLike(Protocol):
    student_id: str

    def evaluate(self, start_slot: int) -> Verdict: ...


class CandidateStatus(str, Enum):
    PENDING = "pending"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"


@dataclass
class NegotiationResult:
    status: str  # "confirmed" | "partial"
    start_slot: int | None
    accept_count: int
    rounds: int
    negotiation_id: str
    member_count: int


@dataclass
class _Candidate:
    slot: int
    score: float
    accept_count: int = 0
    status: CandidateStatus = CandidateStatus.PENDING
    proposed: bool = False


@dataclass
class NegotiateSession:
    """In-process coordinator search over member evaluate() callbacks.

    Persists only per-candidate accept_count / status (no per-member verdicts).
    Ephemeral per-round responses are discarded after aggregating counts.
    """

    group_id: str
    members: list[MemberLike]
    member_tod: list[TimeOfDayWeights]
    log: NegotiationLog
    db_path: str | Path | None = None
    budget: int = PROPOSAL_BUDGET
    negotiation_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if len(self.members) != len(self.member_tod):
            raise ValueError("members and member_tod length mismatch")
        if not self.members:
            raise ValueError("need at least one member")
        self._shift_bonus: dict[int, float] = {}
        self._candidates: dict[int, _Candidate] = {}
        for slot in all_legal_starts():
            score = aggregate_score(slot, self.member_tod, self._shift_bonus.get(slot, 0.0))
            self._candidates[slot] = _Candidate(slot=slot, score=score)
        self._rounds = 0
        self._best_slot: int | None = None
        self._best_accepts = -1
        if self.db_path is not None:
            self._persist_init()

    # --- persistence (aggregate counts only) ---

    def _conn(self) -> sqlite3.Connection:
        assert self.db_path is not None
        return connect(self.db_path)

    def _persist_init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO negotiation_rounds
                  (negotiation_id, group_id, round_number, proposed_slot,
                   accept_count, outcome, budget)
                VALUES (?, ?, 0, NULL, 0, 'init', ?)
                """,
                (self.negotiation_id, self.group_id, self.budget),
            )
            conn.executemany(
                """
                INSERT OR REPLACE INTO negotiation_candidates
                  (negotiation_id, slot, accept_count, status, score)
                VALUES (?, ?, 0, 'pending', ?)
                """,
                [
                    (self.negotiation_id, c.slot, c.score)
                    for c in self._candidates.values()
                ],
            )
            conn.commit()

    def _persist_candidate(self, c: _Candidate) -> None:
        if self.db_path is None:
            return
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE negotiation_candidates
                   SET accept_count = ?, status = ?, score = ?
                 WHERE negotiation_id = ? AND slot = ?
                """,
                (c.accept_count, c.status.value, c.score, self.negotiation_id, c.slot),
            )
            conn.commit()

    def _persist_round(
        self, round_number: int, slot: int, accept_count: int, outcome: str
    ) -> None:
        if self.db_path is None:
            return
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO negotiation_rounds
                  (negotiation_id, group_id, round_number, proposed_slot,
                   accept_count, outcome, budget)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.negotiation_id,
                    self.group_id,
                    round_number,
                    slot,
                    accept_count,
                    outcome,
                    self.budget,
                ),
            )
            conn.commit()

    def _rescore(self, slot: int) -> None:
        c = self._candidates[slot]
        c.score = aggregate_score(
            slot, self.member_tod, self._shift_bonus.get(slot, 0.0)
        )

    def _pick_next(self) -> _Candidate | None:
        pending = [
            c
            for c in self._candidates.values()
            if c.status is CandidateStatus.PENDING
        ]
        if not pending:
            return None
        # Highest score; tie-break lower slot index for determinism.
        return max(pending, key=lambda c: (c.score, -c.slot))

    def _apply_shift_hints(self, deltas: list[int], base_slot: int) -> None:
        for delta in deltas:
            target = base_slot + delta
            if target not in self._candidates:
                continue
            if self._candidates[target].status is not CandidateStatus.PENDING:
                continue
            self._shift_bonus[target] = self._shift_bonus.get(target, 0.0) + SHIFT_HINT_BONUS
            self._rescore(target)
            self._persist_candidate(self._candidates[target])

    def _track_best(self, slot: int, accept_count: int) -> None:
        if accept_count > self._best_accepts or (
            accept_count == self._best_accepts
            and (self._best_slot is None or slot < self._best_slot)
        ):
            self._best_accepts = accept_count
            self._best_slot = slot

    def run(self) -> NegotiationResult:
        n_members = len(self.members)
        while self._rounds < self.budget:
            cand = self._pick_next()
            if cand is None:
                break
            self._rounds += 1
            slot = cand.slot
            cand.proposed = True

            propose = Propose(group_id=self.group_id, start_slot=slot)
            self.log.append(propose.as_dict())

            # Ephemeral per-round responses — discarded after aggregating counts.
            accepts = 0
            any_reject = False
            shift_deltas: list[int] = []
            for member in self.members:
                verdict = member.evaluate(slot)
                respond = Respond(
                    group_id=self.group_id, start_slot=slot, verdict=verdict
                )
                self.log.append(respond.as_dict())
                if verdict.kind is VerdictKind.ACCEPT:
                    accepts += 1
                elif verdict.kind is VerdictKind.REJECT:
                    any_reject = True
                elif verdict.kind is VerdictKind.ACCEPT_IF_SHIFTED:
                    assert verdict.delta is not None
                    shift_deltas.append(verdict.delta)

            cand.accept_count = accepts
            self._track_best(slot, accepts)

            if accepts == n_members and not any_reject and not shift_deltas:
                cand.status = CandidateStatus.CONFIRMED
                self._persist_candidate(cand)
                self._persist_round(self._rounds, slot, accepts, "confirmed")
                confirm = Confirm(group_id=self.group_id, start_slot=slot)
                self.log.append(confirm.as_dict())
                return NegotiationResult(
                    status="confirmed",
                    start_slot=slot,
                    accept_count=accepts,
                    rounds=self._rounds,
                    negotiation_id=self.negotiation_id,
                    member_count=n_members,
                )

            # Not unanimous accept: remove candidate; apply shift hints; continue.
            cand.status = CandidateStatus.REJECTED
            self._persist_candidate(cand)
            self._apply_shift_hints(shift_deltas, slot)
            outcome = "rejected" if any_reject else "no_unanimous"
            self._persist_round(self._rounds, slot, accepts, outcome)

        # Budget exhausted or no candidates left — best partial, never silent confirm.
        return NegotiationResult(
            status="partial",
            start_slot=self._best_slot,
            accept_count=max(self._best_accepts, 0),
            rounds=self._rounds,
            negotiation_id=self.negotiation_id,
            member_count=n_members,
        )


@dataclass
class InProcessMember:
    """Member agent store: availability stays private to this object."""

    student_id: str
    _availability: str
    tod: TimeOfDayWeights = field(default_factory=TimeOfDayWeights)

    def evaluate(self, start_slot: int) -> Verdict:
        from standing.negotiation.member_eval import evaluate as _evaluate

        return _evaluate(start_slot, self._availability)
