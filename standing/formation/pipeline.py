"""Formation pipeline: greedy → local search → negotiate → keep CONFIRMed only."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from standing.formation.greedy import greedy_seed
from standing.formation.local_search import (
    DEFAULT_ITERS,
    DEFAULT_SEED,
    local_search,
)
from standing.formation.objective import FormationStudent, partition_score
from standing.models import TimeOfDayWeights
from standing.negotiation.coordinator_negotiate import (
    InProcessMember,
    NegotiateSession,
)
from standing.negotiation.log import NegotiationLog
from standing.negotiation.messages import Verdict, VerdictKind


class MemberLike(Protocol):
    student_id: str

    def evaluate(self, start_slot: int) -> Verdict: ...


NegotiatorFn = Callable[
    [str, list[MemberLike], list[TimeOfDayWeights]],
    tuple[bool, int | None],
]


@dataclass(frozen=True)
class FormedGroup:
    group_id: str
    course_code: str
    member_ids: tuple[str, ...]
    confirmed_slot: int


@dataclass
class FormationResult:
    groups: list[FormedGroup]
    objective_before: float
    objective_after: float
    unplaced: list[str] = field(default_factory=list)
    rejected_candidates: list[str] = field(default_factory=list)


def _default_negotiator(
    group_id: str,
    members: list[MemberLike],
    member_tod: list[TimeOfDayWeights],
    *,
    log_dir: Path | None = None,
) -> tuple[bool, int | None]:
    log_path = (log_dir or Path(".")) / f"neg_{group_id}.jsonl"
    session = NegotiateSession(
        group_id=group_id,
        members=members,
        member_tod=member_tod,
        log=NegotiationLog(log_path),
        budget=40,
    )
    result = session.run()
    if result.status == "confirmed" and result.start_slot is not None:
        return True, result.start_slot
    return False, None


def always_confirm_stub(
    group_id: str,
    members: list[MemberLike],
    member_tod: list[TimeOfDayWeights],
) -> tuple[bool, int | None]:
    """Test stub: every candidate CONFIRMs at slot 0."""
    return True, 0


def never_confirm_stub(
    group_id: str,
    members: list[MemberLike],
    member_tod: list[TimeOfDayWeights],
) -> tuple[bool, int | None]:
    """Test stub: never finds a slot."""
    return False, None


def form_groups(
    pool: Sequence[FormationStudent],
    members_by_id: Mapping[str, MemberLike],
    member_tod: Mapping[str, TimeOfDayWeights] | None = None,
    *,
    seed: int = DEFAULT_SEED,
    iters: int = DEFAULT_ITERS,
    negotiator: NegotiatorFn | None = None,
    log_dir: Path | None = None,
) -> FormationResult:
    """Greedy → local search → negotiate; emit CONFIRM groups only (no bitmaps in soft score)."""
    students = {s.student_id: s for s in pool}
    seeded, unplaced0 = greedy_seed(pool)
    obj_before = partition_score([m for _, _, m in seeded], students)

    improved, unplaced, _sb, obj_after = local_search(
        seeded, unplaced0, students, seed=seed, iters=iters
    )
    obj_before = _sb

    neg = negotiator
    if neg is None:

        def neg(
            gid: str,
            mems: list[MemberLike],
            tods: list[TimeOfDayWeights],
        ) -> tuple[bool, int | None]:
            return _default_negotiator(gid, mems, tods, log_dir=log_dir)

    tod_map = member_tod or {}
    formed: list[FormedGroup] = []
    rejected: list[str] = []
    confirmed_ids: set[str] = set()

    for gid, course, member_ids in improved:
        mems: list[MemberLike] = []
        tods: list[TimeOfDayWeights] = []
        ok = True
        for sid in member_ids:
            m = members_by_id.get(sid)
            if m is None:
                ok = False
                break
            mems.append(m)
            if sid in tod_map:
                tods.append(tod_map[sid])
            elif isinstance(m, InProcessMember):
                tods.append(m.tod)
            else:
                tods.append(TimeOfDayWeights())
        if not ok:
            rejected.append(gid)
            continue
        confirmed, slot = neg(gid, mems, tods)
        if confirmed and slot is not None:
            formed.append(
                FormedGroup(
                    group_id=gid,
                    course_code=course,
                    member_ids=tuple(sorted(member_ids)),
                    confirmed_slot=slot,
                )
            )
            confirmed_ids.update(member_ids)
        else:
            rejected.append(gid)

    still_unplaced = sorted(
        sid for sid in students if sid not in confirmed_ids
    )
    return FormationResult(
        groups=formed,
        objective_before=obj_before,
        objective_after=obj_after,
        unplaced=still_unplaced,
        rejected_candidates=rejected,
    )
