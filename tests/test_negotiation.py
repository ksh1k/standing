"""Phase 2 negotiation protocol tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from standing.constants import SLOTS_PER_WEEK
from standing.db import apply_coordinator_migrations, connect, list_tables
from standing.models import TimeOfDayWeights
from standing.negotiation.coordinator_negotiate import (
    InProcessMember,
    NegotiateSession,
    PROPOSAL_BUDGET,
)
from standing.negotiation.log import NegotiationLog
from standing.negotiation.messages import VerdictKind
from standing.negotiation.search import all_legal_starts
from tests.fixtures.five_students import (
    EXPECTED_UNANIMOUS_SLOT,
    GROUP_TOD,
    STUDENT_IDS,
    build_five_members,
    build_five_student_bitmaps,
)


def _busy_bitmap() -> str:
    return "0" * SLOTS_PER_WEEK


def _free_only(starts: list[int]) -> str:
    bits = ["0"] * SLOTS_PER_WEEK
    for s in starts:
        bits[s] = bits[s + 1] = bits[s + 2] = "1"
    return "".join(bits)


def test_fixture_documents_expected_slot() -> None:
    assert EXPECTED_UNANIMOUS_SLOT == 78
    bitmaps = build_five_student_bitmaps()
    assert set(bitmaps) == set(STUDENT_IDS)


def test_five_student_negotiation_confirms_expected_slot(tmp_path: Path) -> None:
    """Fixture confirms documented unanimous slot."""
    log_path = tmp_path / "negotiation_log.jsonl"
    db_path = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db_path)

    members = build_five_members()
    tod = [GROUP_TOD] * len(members)
    session = NegotiateSession(
        group_id="g-five",
        members=members,
        member_tod=tod,
        log=NegotiationLog(log_path),
        db_path=db_path,
    )
    result = session.run()

    assert result.status == "confirmed"
    assert result.start_slot == EXPECTED_UNANIMOUS_SLOT
    assert result.accept_count == 5
    assert result.rounds >= 2  # decoys rejected before confirm (not first-pick)

    records = NegotiationLog(log_path).read_all()
    types = [r["type"] for r in records]
    assert "PROPOSE" in types
    assert "RESPOND" in types
    assert "CONFIRM" in types
    confirm = next(r for r in records if r["type"] == "CONFIRM")
    assert confirm["start_slot"] == EXPECTED_UNANIMOUS_SLOT


def test_rejected_member_prevents_confirm(tmp_path: Path) -> None:
    """Any reject → no CONFIRM for that slot."""
    log_path = tmp_path / "negotiation_log.jsonl"
    a = InProcessMember("a", _free_only([0]), TimeOfDayWeights())
    b = InProcessMember("b", _busy_bitmap(), TimeOfDayWeights())
    session = NegotiateSession(
        group_id="g-reject",
        members=[a, b],
        member_tod=[TimeOfDayWeights(), TimeOfDayWeights()],
        log=NegotiationLog(log_path),
        budget=5,
    )
    result = session.run()
    assert result.status == "partial"
    records = NegotiationLog(log_path).read_all()
    assert all(r["type"] != "CONFIRM" for r in records)
    proposes_0 = [
        r for r in records if r["type"] == "PROPOSE" and r["start_slot"] == 0
    ]
    assert proposes_0
    responds_0 = [
        r for r in records if r["type"] == "RESPOND" and r["start_slot"] == 0
    ]
    assert any(r["verdict"]["kind"] == "reject" for r in responds_0)
    assert any(r["verdict"]["kind"] == "accept" for r in responds_0)


def test_accept_if_shifted_reweights_and_finds_shifted_window(tmp_path: Path) -> None:
    """Shift hints boost hinted slot → CONFIRM shifted start."""
    log_path = tmp_path / "negotiation_log.jsonl"
    tod = TimeOfDayWeights(morning=1.0, afternoon=1.0, evening=1.0)
    bitmap = _free_only([12])
    members = [
        InProcessMember("a", bitmap, tod),
        InProcessMember("b", bitmap, tod),
    ]
    session = NegotiateSession(
        group_id="g-shift",
        members=members,
        member_tod=[tod, tod],
        log=NegotiationLog(log_path),
        budget=40,
    )
    result = session.run()
    assert result.status == "confirmed"
    assert result.start_slot == 12

    records = NegotiationLog(log_path).read_all()
    shifted = [
        r
        for r in records
        if r["type"] == "RESPOND"
        and r["verdict"]["kind"] == VerdictKind.ACCEPT_IF_SHIFTED.value
    ]
    assert shifted, "expected at least one accept_if_shifted toward slot 12"


def test_budget_returns_best_partial_without_confirm(tmp_path: Path) -> None:
    """Budget exhaust → partial, no CONFIRM."""
    log_path = tmp_path / "negotiation_log.jsonl"
    tod = TimeOfDayWeights(morning=3.0, afternoon=1.0, evening=1.0)
    members = [
        InProcessMember("m0", _free_only([10]), tod),
        InProcessMember("m1", _free_only([10, 14]), tod),
        InProcessMember("m2", _free_only([14]), tod),
    ]
    session = NegotiateSession(
        group_id="g-partial",
        members=members,
        member_tod=[tod, tod, tod],
        log=NegotiationLog(log_path),
        budget=PROPOSAL_BUDGET,
    )
    result = session.run()
    assert result.status == "partial"
    assert result.accept_count == 2
    assert result.start_slot in (10, 14)
    assert result.rounds == PROPOSAL_BUDGET or result.rounds <= PROPOSAL_BUDGET
    records = NegotiationLog(log_path).read_all()
    assert all(r["type"] != "CONFIRM" for r in records)


def test_negotiation_persists_candidate_counts_not_per_member(tmp_path: Path) -> None:
    db_path = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db_path)
    members = build_five_members()
    session = NegotiateSession(
        group_id="g-persist",
        members=members,
        member_tod=[GROUP_TOD] * 5,
        log=NegotiationLog(tmp_path / "log.jsonl"),
        db_path=db_path,
    )
    session.run()
    with connect(db_path) as conn:
        tables = list_tables(conn)
        assert "negotiation_candidates" in tables
        assert "negotiation_rounds" in tables
        # No per-member verdict table.
        assert not any("verdict" in t for t in tables)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(negotiation_candidates)")}
        assert "accept_count" in cols
        assert "student_id" not in cols
