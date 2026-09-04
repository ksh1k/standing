"""Structural tests for hard constraints 2, 3, and 4."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from standing.db import (
    COORDINATOR_MIGRATIONS,
    MEMBER_MIGRATION,
    apply_coordinator_migrations,
    apply_member_migrations,
    list_tables,
    table_columns,
)

# Forbidden residence-related column name fragments (constraint 2)
RESIDENCE_PATTERNS = re.compile(
    r"(address|dorm|apartment|residence|home_?loc|building_of_residence|street|zip.?code)",
    re.IGNORECASE,
)


def _all_column_names(conn: sqlite3.Connection) -> list[str]:
    names: list[str] = []
    for table in list_tables(conn):
        names.extend(table_columns(conn, table))
    return names


def test_constraint2_no_residence_columns_in_member_schema(tmp_path: Path) -> None:
    db = tmp_path / "member.db"
    apply_member_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cols = _all_column_names(conn)
    conn.close()
    offenders = [c for c in cols if RESIDENCE_PATTERNS.search(c)]
    assert offenders == [], f"Residence-related columns in member schema: {offenders}"


def test_constraint2_no_residence_columns_in_coordinator_schema(tmp_path: Path) -> None:
    db = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cols = _all_column_names(conn)
    conn.close()
    offenders = [c for c in cols if RESIDENCE_PATTERNS.search(c)]
    assert offenders == [], f"Residence-related columns in coordinator schema: {offenders}"


def test_constraint2_no_residence_in_sql_source() -> None:
    for path in (MEMBER_MIGRATION, *COORDINATOR_MIGRATIONS):
        text = path.read_text(encoding="utf-8")
        # Ignore SQL comment lines when scanning for forbidden identifiers as columns
        code_lines = [
            ln for ln in text.splitlines() if not ln.strip().startswith("--")
        ]
        joined = "\n".join(code_lines)
        assert not RESIDENCE_PATTERNS.search(joined), (
            f"Residence-related identifier in non-comment SQL of {path.name}"
        )


def test_constraint3_member_has_availability(tmp_path: Path) -> None:
    db = tmp_path / "member.db"
    apply_member_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cols = table_columns(conn, "student_profile")
    conn.close()
    assert "availability" in cols


def test_constraint3_coordinator_students_no_availability(tmp_path: Path) -> None:
    db = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cols = table_columns(conn, "students")
    conn.close()
    assert "availability" not in cols


def test_constraint4_attendance_only_in_member(tmp_path: Path) -> None:
    member_db = tmp_path / "member.db"
    coord_db = tmp_path / "coordinator.db"
    apply_member_migrations(member_db)
    apply_coordinator_migrations(coord_db)

    mconn = sqlite3.connect(member_db)
    mconn.row_factory = sqlite3.Row
    mtables = list_tables(mconn)
    mconn.close()
    assert "attendance" in mtables

    cconn = sqlite3.connect(coord_db)
    cconn.row_factory = sqlite3.Row
    ctables = list_tables(cconn)
    session_cols = table_columns(cconn, "sessions")
    cconn.close()

    assert "attendance" not in ctables
    attended_like = [c for c in session_cols if "attend" in c.lower()]
    assert attended_like == [], f"Coordinator sessions has attendance columns: {attended_like}"
