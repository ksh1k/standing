"""Phase 5 persistence: time-travel tests (injectible now; never sleep)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from standing.db import apply_coordinator_migrations, apply_member_migrations, connect
from standing.negotiation.coordinator_negotiate import NegotiateSession
from standing.negotiation.log import NegotiationLog
from standing.persistence.dormancy import (
    check_dormancy,
    consecutive_miss_count,
    is_dormant,
)
from standing.persistence.drift import check_drift, consecutive_low_streak, session_low
from standing.persistence.exam_season import adapt_exam_season, in_exam_window
from standing.persistence.reminders import check_reminders, reminder_due
from standing.persistence.repair import check_repair, count_active_from_flags
from standing.persistence.clock import to_iso
from tests.fixtures.five_students import (
    EXPECTED_UNANIMOUS_SLOT,
    GROUP_TOD,
    build_five_members,
)

UTC = timezone.utc
SESSION_DT = datetime(2026, 9, 10, 18, 0, tzinfo=UTC)  # Thu 18:00


def _member_db(tmp: Path, student_id: str = "s0") -> Path:
    db = tmp / f"member_{student_id}.db"
    apply_member_migrations(db)
    with connect(db) as conn:
        conn.execute(
            """
            INSERT INTO student_profile (
                student_id, display_name, year, courses, availability,
                preferred_group_size, preferred_zones, study_style
            ) VALUES (?, ?, 'junior', '["CSCE315"]', ?, 4, '["main_library"]', 'discussion')
            """,
            (student_id, student_id, "0" * 224),
        )
        conn.commit()
    return db


def _add_local_session(
    db: Path, session_id: str, when: datetime, location: str = "main_library"
) -> None:
    with connect(db) as conn:
        conn.execute(
            """
            INSERT INTO local_sessions (session_id, group_id, scheduled_datetime, location)
            VALUES (?, 'g1', ?, ?)
            """,
            (session_id, to_iso(when), location),
        )
        conn.commit()


def _record_attendance(db: Path, student_id: str, session_id: str, attended: int) -> None:
    with connect(db) as conn:
        conn.execute(
            """
            INSERT INTO attendance (student_id, session_id, attended)
            VALUES (?, ?, ?)
            """,
            (student_id, session_id, attended),
        )
        conn.commit()


def _coord_db(tmp: Path) -> Path:
    db = tmp / "coord.db"
    apply_coordinator_migrations(db)
    with connect(db) as conn:
        for sid in ("s0", "s1", "s2", "s3", "s4"):
            conn.execute(
                """
                INSERT INTO students (
                    student_id, year, courses, preferred_group_size,
                    preferred_zones, study_style
                ) VALUES (?, 'junior', '["CSCE315"]', 4, '["main_library"]', 'discussion')
                """,
                (sid,),
            )
        conn.execute(
            """
            INSERT INTO groups (
                group_id, course_code, member_ids, scheduled_slot, zone, status
            ) VALUES (
                'g1', 'CSCE315', ?, 78, 'main_library', 'active'
            )
            """,
            (json.dumps(["s0", "s1", "s2", "s3", "s4"]),),
        )
        conn.commit()
    return db


def _add_coord_session(
    db: Path,
    session_id: str,
    when: datetime,
    attended: int | None = None,
    total: int = 5,
    kind: str = "regular",
    group_id: str = "g1",
) -> None:
    with connect(db) as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, group_id, scheduled_datetime, location)
            VALUES (?, ?, ?, 'main_library')
            """,
            (session_id, group_id, to_iso(when)),
        )
        conn.execute(
            "INSERT INTO session_kinds (session_id, kind) VALUES (?, ?)",
            (session_id, kind),
        )
        if attended is not None:
            conn.execute(
                """
                INSERT INTO session_aggregates (session_id, attended_count, member_total)
                VALUES (?, ?, ?)
                """,
                (session_id, attended, total),
            )
        conn.commit()


# --- reminders ---


def test_reminder_due_exactly_at_24h_not_earlier() -> None:
    assert reminder_due(SESSION_DT, SESSION_DT - timedelta(hours=24))
    assert not reminder_due(SESSION_DT, SESSION_DT - timedelta(hours=24, seconds=1))
    assert not reminder_due(SESSION_DT, SESSION_DT)  # at/after session: no


def test_reminder_fires_at_24h_window(tmp_path: Path) -> None:
    db = _member_db(tmp_path)
    _add_local_session(db, "sess-a", SESSION_DT)
    early = SESSION_DT - timedelta(hours=25)
    assert check_reminders(db, "s0", early) == []
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"] == 0

    at_lead = SESSION_DT - timedelta(hours=24)
    created = check_reminders(db, "s0", at_lead)
    assert len(created) == 1 and created[0].created
    with connect(db) as conn:
        rows = conn.execute("SELECT kind, session_id FROM notifications").fetchall()
        assert len(rows) == 1
        assert rows[0]["kind"] == "reminder"
        assert rows[0]["session_id"] == "sess-a"
    # idempotent
    again = check_reminders(db, "s0", at_lead)
    assert again[0].created is False


# --- dormancy ---


def test_dormancy_after_exactly_three_consecutive_misses(tmp_path: Path) -> None:
    assert consecutive_miss_count([1, 0, 0]) == 2
    assert not is_dormant([1, 0, 0])
    assert consecutive_miss_count([0, 0, 0]) == 3
    assert is_dormant([0, 0, 0])
    assert consecutive_miss_count([0, 0, 0, 1, 0]) == 1

    db = _member_db(tmp_path)
    base = SESSION_DT
    for i, attended in enumerate([0, 0]):
        sid = f"m{i}"
        _add_local_session(db, sid, base + timedelta(weeks=i))
        _record_attendance(db, "s0", sid, attended)
    now = base + timedelta(weeks=2)
    r = check_dormancy(db, "s0", now)
    assert r.notified is False
    assert r.consecutive_misses == 2

    _add_local_session(db, "m2", base + timedelta(weeks=2))
    _record_attendance(db, "s0", "m2", 0)
    r3 = check_dormancy(db, "s0", now)
    assert r3.notified is True
    assert r3.private is True
    assert r3.consecutive_misses == 3
    with connect(db) as conn:
        notes = conn.execute(
            "SELECT kind FROM notifications WHERE student_id='s0'"
        ).fetchall()
        assert len(notes) == 1
        assert notes[0]["kind"] == "dormancy_checkin"
        # private only — no group announcement table / kind
        assert all(n["kind"] != "group_announce" for n in notes)


def test_dormancy_private_only_no_coord_side_effect(tmp_path: Path) -> None:
    mdb = _member_db(tmp_path)
    cdb = _coord_db(tmp_path)
    base = SESSION_DT
    for i in range(3):
        sid = f"d{i}"
        _add_local_session(mdb, sid, base + timedelta(weeks=i))
        _record_attendance(mdb, "s0", sid, 0)
    check_dormancy(mdb, "s0", base + timedelta(weeks=3))
    with connect(cdb) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM drift_events").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) AS n FROM merge_flags").fetchone()["n"] == 0


# --- drift ---


def test_drift_triggers_renegotiation_with_fixture_bitmaps(tmp_path: Path) -> None:
    assert session_low(2, 5) is True
    assert session_low(3, 5) is False
    assert consecutive_low_streak([(2, 5), (1, 5), (2, 5)]) == 3
    assert consecutive_low_streak([(2, 5), (1, 5), (4, 5)]) == 0

    cdb = _coord_db(tmp_path)
    base = SESSION_DT
    for i in range(3):
        _add_coord_session(cdb, f"low{i}", base + timedelta(weeks=i), attended=2, total=5)

    calls: list[str] = []

    def renegotiate(group_id: str):
        calls.append(group_id)
        members = build_five_members()
        log = NegotiationLog(tmp_path / "drift_renegotiate.jsonl")
        session = NegotiateSession(
            group_id=group_id,
            members=members,
            member_tod=[GROUP_TOD] * 5,
            log=log,
            db_path=cdb,
        )
        return session.run()

    # Only two lows → no trigger
    two = tmp_path / "two"
    two.mkdir()
    cdb2 = _coord_db(two)
    for i in range(2):
        _add_coord_session(cdb2, f"t{i}", base + timedelta(weeks=i), attended=1, total=5)
    r2 = check_drift(cdb2, "g1", base, renegotiate=renegotiate)
    assert r2.triggered is False
    assert calls == []

    now = base + timedelta(weeks=3)
    result = check_drift(cdb, "g1", now, renegotiate=renegotiate)
    assert result.triggered is True
    assert result.consecutive_low == 3
    assert calls == ["g1"]
    assert result.status == "renegotiated"
    assert result.new_slot == EXPECTED_UNANIMOUS_SLOT
    with connect(cdb) as conn:
        slot = conn.execute(
            "SELECT scheduled_slot FROM groups WHERE group_id='g1'"
        ).fetchone()["scheduled_slot"]
        assert slot == EXPECTED_UNANIMOUS_SLOT
        ev = conn.execute("SELECT status FROM drift_events").fetchone()
        assert ev["status"] == "renegotiated"


# --- exam season ---


def test_exam_season_adds_second_session_and_removes_after(tmp_path: Path) -> None:
    exam = datetime(2026, 10, 1, tzinfo=UTC).date()
    assert in_exam_window(exam, datetime(2026, 9, 17, tzinfo=UTC))
    assert in_exam_window(exam, datetime(2026, 9, 30, tzinfo=UTC))
    assert not in_exam_window(exam, datetime(2026, 9, 16, tzinfo=UTC))
    assert not in_exam_window(exam, datetime(2026, 10, 1, tzinfo=UTC))

    cdb = _coord_db(tmp_path)
    _add_coord_session(cdb, "primary", SESSION_DT, attended=5, total=5)
    with connect(cdb) as conn:
        conn.execute(
            "INSERT INTO exam_dates (course_code, exam_date) VALUES ('CSCE315', '2026-10-01')"
        )
        conn.commit()

    before = datetime(2026, 9, 10, tzinfo=UTC)
    r0 = adapt_exam_season(cdb, "g1", before)
    assert r0.in_window is False
    assert r0.added_session_id is None

    in_win = datetime(2026, 9, 20, tzinfo=UTC)
    r1 = adapt_exam_season(cdb, "g1", in_win)
    assert r1.in_window is True
    assert r1.added_session_id is not None
    with connect(cdb) as conn:
        kinds = conn.execute(
            "SELECT kind FROM session_kinds WHERE session_id=?",
            (r1.added_session_id,),
        ).fetchone()
        assert kinds["kind"] == "exam_season"
        n = conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]
        assert n == 2

    # idempotent while in window
    r1b = adapt_exam_season(cdb, "g1", in_win)
    assert r1b.added_session_id is None

    after = datetime(2026, 10, 2, tzinfo=UTC)
    r2 = adapt_exam_season(cdb, "g1", after)
    assert r2.in_window is False
    assert r1.added_session_id in r2.removed_session_ids
    with connect(cdb) as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]
        assert n == 1
        kind_left = conn.execute("SELECT kind FROM session_kinds").fetchall()
        assert all(k["kind"] == "regular" for k in kind_left)


# --- repair ---


def test_repair_flag_when_active_members_below_four(tmp_path: Path) -> None:
    flags = {
        "a": [0, 0, 0],  # dormant
        "b": [1, 1, 1],
        "c": [1, 0, 1],
        "d": [0, 0],  # not yet dormant
        "e": [0, 0, 0],  # dormant
    }
    assert count_active_from_flags(flags) == 3  # b,c,d

    cdb = _coord_db(tmp_path)
    now = SESSION_DT
    ok = check_repair(cdb, "g1", active_member_count=5, now=now)
    assert ok.flagged is False
    with connect(cdb) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM merge_flags").fetchone()["n"] == 0

    bad = check_repair(cdb, "g1", active_member_count=3, now=now)
    assert bad.flagged is True
    assert bad.course_code == "CSCE315"
    with connect(cdb) as conn:
        row = conn.execute("SELECT * FROM merge_flags WHERE group_id='g1'").fetchone()
        assert row["active_member_count"] == 3
        assert "below" in row["reason"]


def test_phase5_migrations_tables(tmp_path: Path) -> None:
    mdb = tmp_path / "m.db"
    cdb = tmp_path / "c.db"
    apply_member_migrations(mdb)
    apply_coordinator_migrations(cdb)
    with connect(mdb) as conn:
        tables = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "notifications" in tables
        assert "local_sessions" in tables
    with connect(cdb) as conn:
        tables = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "session_aggregates" in tables
        assert "exam_dates" in tables
        assert "drift_events" in tables
        assert "merge_flags" in tables
