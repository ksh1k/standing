"""Fails if the coordinator schema gains an availability column (constraint 3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from standing.db import apply_coordinator_migrations, list_tables, table_columns


def test_coordinator_has_no_availability_column_anywhere(tmp_path: Path) -> None:
    db = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    offenders: list[str] = []
    for table in list_tables(conn):
        for col in table_columns(conn, table):
            if col.lower() == "availability" or "availability" in col.lower():
                offenders.append(f"{table}.{col}")
    conn.close()
    assert offenders == [], (
        "Coordinator DB must never store availability bitmaps; found: " + ", ".join(offenders)
    )


def test_coordinator_students_expected_columns_only(tmp_path: Path) -> None:
    """students table: student_id, year, courses, preferred_group_size, preferred_zones, study_style (+ created_at)."""
    db = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cols = set(table_columns(conn, "students"))
    conn.close()
    required = {
        "student_id",
        "year",
        "courses",
        "preferred_group_size",
        "preferred_zones",
        "study_style",
    }
    assert required <= cols
    assert "availability" not in cols
    assert "display_name" not in cols  # display_name stays on member side
