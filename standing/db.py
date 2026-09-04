"""SQLite helpers: apply SQL migrations to member / coordinator databases.

No ORM. Schema lives in standing/migrations/*.sql.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

MEMBER_MIGRATION = MIGRATIONS_DIR / "001_member.sql"
COORDINATOR_MIGRATION = MIGRATIONS_DIR / "001_coordinator.sql"


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def apply_member_migrations(db_path: str | Path) -> None:
    """Create / migrate the member-agent database."""
    sql = _read_sql(MEMBER_MIGRATION)
    with connect(db_path) as conn:
        conn.executescript(sql)
        conn.commit()


def apply_coordinator_migrations(db_path: str | Path) -> None:
    """Create / migrate the coordinator-agent database."""
    sql = _read_sql(COORDINATOR_MIGRATION)
    with connect(db_path) as conn:
        conn.executescript(sql)
        conn.commit()


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return column names for a table (for tests / introspection)."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r["name"] for r in rows]


def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]
