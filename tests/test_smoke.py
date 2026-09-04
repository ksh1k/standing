"""Smoke tests: migrations apply; apps import."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from standing.db import (
    apply_coordinator_migrations,
    apply_member_migrations,
    list_tables,
)
from standing.coordinator.app import app as coordinator_app
from standing.member.app import app as member_app


def test_member_migrations_apply(tmp_path: Path) -> None:
    db = tmp_path / "member.db"
    apply_member_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    tables = list_tables(conn)
    conn.close()
    assert "student_profile" in tables
    assert "attendance" in tables
    assert "notifications" in tables
    assert "local_sessions" in tables


def test_coordinator_migrations_apply(tmp_path: Path) -> None:
    db = tmp_path / "coordinator.db"
    apply_coordinator_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    tables = list_tables(conn)
    conn.close()
    assert "students" in tables
    assert "groups" in tables
    assert "sessions" in tables
    assert "negotiation_candidates" in tables
    assert "negotiation_rounds" in tables
    assert "session_aggregates" in tables
    assert "merge_flags" in tables


def test_coordinator_app_imports() -> None:
    assert coordinator_app.title == "Standing Coordinator"
    paths = {r.path for r in coordinator_app.routes if hasattr(r, "path")}
    assert "/healthz" in paths
    assert "/api/transcript" in paths
    assert "/api/groups" in paths
    assert "/api/demo/negotiate" in paths


def test_member_app_imports() -> None:
    assert member_app.title == "Standing Member Agent"
    paths = {r.path for r in member_app.routes if hasattr(r, "path")}
    assert "/healthz" in paths
    assert "/api/intake" in paths
    assert "/api/groups" in paths
    assert "/api/notifications" in paths
