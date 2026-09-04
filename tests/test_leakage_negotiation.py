"""Leakage tests: coordinator persisted state must not reveal unproposed availability."""

from __future__ import annotations

import json
from pathlib import Path

from standing.db import apply_coordinator_migrations, connect, list_tables, table_columns
from standing.negotiation.coordinator_negotiate import NegotiateSession
from standing.negotiation.log import NegotiationLog
from standing.negotiation.search import all_legal_starts
from tests.fixtures.five_students import (
    EXPECTED_UNANIMOUS_SLOT,
    GROUP_TOD,
    STUDENT_IDS,
    build_five_members,
    build_five_student_bitmaps,
)


def test_coordinator_schema_still_has_no_availability(tmp_path: Path) -> None:
    db = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db)
    with connect(db) as conn:
        offenders: list[str] = []
        for table in list_tables(conn):
            for col in table_columns(conn, table):
                if "availability" in col.lower():
                    offenders.append(f"{table}.{col}")
        assert offenders == []


def test_post_negotiation_state_hides_unproposed_availability(tmp_path: Path) -> None:
    """After a full negotiation, coordinator SQLite state must not let an observer
    derive a member's free/busy for any *unproposed* slot.

    We only persist per-candidate accept_count / status / score — never
    per-member verdicts. Unproposed pending rows share accept_count=0 / pending
    regardless of whether a member would have accepted them.
    """
    db_path = tmp_path / "coordinator.db"
    log_path = tmp_path / "negotiation_log.jsonl"
    apply_coordinator_migrations(db_path)

    bitmaps = build_five_student_bitmaps()
    members = build_five_members()
    session = NegotiateSession(
        group_id="g-leak",
        members=members,
        member_tod=[GROUP_TOD] * len(members),
        log=NegotiationLog(log_path),
        db_path=db_path,
    )
    result = session.run()
    assert result.status == "confirmed"
    assert result.start_slot == EXPECTED_UNANIMOUS_SLOT

    with connect(db_path) as conn:
        for table in list_tables(conn):
            cols = [c.lower() for c in table_columns(conn, table)]
            assert "availability" not in cols
            if table.startswith("negotiation"):
                assert "student_id" not in cols
                assert "verdict" not in cols
                assert "member_id" not in cols

        proposed_slots = {
            row["proposed_slot"]
            for row in conn.execute(
                "SELECT proposed_slot FROM negotiation_rounds "
                "WHERE proposed_slot IS NOT NULL"
            )
        }
        assert EXPECTED_UNANIMOUS_SLOT in proposed_slots

        pending = conn.execute(
            """
            SELECT slot, accept_count, status, score
              FROM negotiation_candidates
             WHERE negotiation_id = ? AND status = 'pending'
             ORDER BY slot
            """,
            (result.negotiation_id,),
        ).fetchall()
        pending_by_slot = {r["slot"]: r for r in pending}

        unproposed = [s for s in all_legal_starts() if s not in proposed_slots]
        assert unproposed, "expected some unproposed legal starts"

        s0 = bitmaps[STUDENT_IDS[0]]
        free_unproposed = [
            s
            for s in unproposed
            if s0[s] == "1" and s0[s + 1] == "1" and s0[s + 2] == "1"
        ]
        busy_unproposed = [
            s
            for s in unproposed
            if not (s0[s] == "1" and s0[s + 1] == "1" and s0[s + 2] == "1")
        ]

        for s in unproposed:
            row = pending_by_slot[s]
            assert row["status"] == "pending"
            assert row["accept_count"] == 0

        if free_unproposed and busy_unproposed:
            a = pending_by_slot[free_unproposed[0]]
            b = pending_by_slot[busy_unproposed[0]]
            assert a["accept_count"] == b["accept_count"] == 0
            assert a["status"] == b["status"] == "pending"

        dump_parts: list[str] = []
        for table in list_tables(conn):
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            dump_parts.append(json.dumps([dict(r) for r in rows], default=str))
        blob = "\n".join(dump_parts)
        for bm in bitmaps.values():
            assert bm not in blob
