"""Product MVP: register/login, course pools, match → confirmed group."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from standing.constants import CampusZone, StudyStyle, YearLevel
from standing.db import apply_coordinator_migrations, connect, table_columns
from tests.fixtures.five_students import STUDENT_IDS, build_five_student_bitmaps


@pytest.fixture()
def product_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "data"
    data.mkdir()
    import standing.coordinator.app as capp
    import standing.member.app as mapp

    for mod in (capp, mapp):
        monkeypatch.setattr(mod, "DATA_DIR", data)
        monkeypatch.setattr(mod, "MEMBER_DB", data / "member.db")
        monkeypatch.setattr(mod, "COORD_DB", data / "coordinator.db")
    monkeypatch.setattr(capp, "LOG_PATH", data / "negotiation_log.jsonl")
    capp._ensure_coord_db()
    capp._ensure_member_db()
    mapp._ensure_db()
    return capp, mapp


def _intake(mapp, sid: str, name: str, course: str, availability: str) -> None:
    from standing.member.app import IntakeRequest

    body = IntakeRequest(
        student_id=sid,
        display_name=name,
        year=YearLevel.JUNIOR,
        courses=[course],
        preferred_group_size=5,
        preferred_zones=[CampusZone.MAIN_LIBRARY],
        study_style=StudyStyle.DISCUSSION,
        time_of_day_preference={"morning": 0.5, "afternoon": 5.0, "evening": 0.5},
        availability=availability,
    )
    assert mapp.api_intake(body)["status"] == "ok"


def test_register_login_and_idempotent(product_env) -> None:
    capp, _ = product_env
    from standing.coordinator.app import AuthLoginRequest, AuthRegisterRequest

    reg = capp.api_auth_register(
        AuthRegisterRequest(student_code="alex27", display_name="Alex")
    )
    assert reg["status"] == "created"
    assert reg["student_id"] == "alex27"
    assert reg["profile"]["display_name"] == "Alex"
    assert "availability" not in reg["profile"]

    again = capp.api_auth_register(
        AuthRegisterRequest(student_id="alex27", display_name="Alexandra")
    )
    assert again["status"] == "exists"
    assert again["profile"]["display_name"] == "Alexandra"

    login = capp.api_auth_login(AuthLoginRequest(student_code="alex27"))
    assert login["status"] == "ok"
    assert login["profile"]["student_code"] == "alex27"
    assert login["profile"]["display_name"] == "Alexandra"
    blob = json.dumps(login)
    assert '"availability":' not in blob  # no raw bitmap field
    assert login["profile"]["has_availability"] is True

    with pytest.raises(HTTPException) as exc:
        capp.api_auth_login(AuthLoginRequest(student_id="missing"))
    assert exc.value.status_code == 404


def test_intake_syncs_coordinator_without_availability(product_env) -> None:
    capp, mapp = product_env
    from standing.coordinator.app import AuthRegisterRequest

    capp.api_auth_register(AuthRegisterRequest(student_code="s9", display_name="Sam"))
    _intake(mapp, "s9", "Sam", "CSCE315", "1" * 224)
    with connect(capp.COORD_DB) as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", ("s9",)
        ).fetchone()
        cols = set(table_columns(conn, "students"))
        assert "availability" not in cols
        assert row is not None
        assert "CSCE315" in json.loads(row["courses"])
        assert "availability" not in row.keys()


def test_join_requires_complete_profile(product_env) -> None:
    capp, mapp = product_env
    from standing.coordinator.app import AuthRegisterRequest, PoolJoinRequest

    capp.api_auth_register(AuthRegisterRequest(student_code="s0", display_name="S0"))
    with pytest.raises(HTTPException) as ei:
        capp.api_pools_join(PoolJoinRequest(student_id="s0", course_code="CSCE315"))
    assert ei.value.status_code == 400

    _intake(mapp, "s0", "S0", "CSCE315", "1" * 224)
    joined = capp.api_pools_join(PoolJoinRequest(student_id="s0", course_code="csce315"))
    assert joined["status"] == "ok"
    assert joined["course_code"] == "CSCE315"
    assert joined["waiting_count"] == 1


def test_join_pool_and_match_confirmed(product_env) -> None:
    capp, mapp = product_env
    from standing.coordinator.app import (
        AuthRegisterRequest,
        PoolJoinRequest,
        PoolMatchRequest,
    )

    course = "CSCE315"
    bitmaps = build_five_student_bitmaps()
    for i, sid in enumerate(STUDENT_IDS):
        capp.api_auth_register(
            AuthRegisterRequest(student_code=sid, display_name=f"Student{i}")
        )
        _intake(mapp, sid, f"Student{i}", course, bitmaps[sid])
        joined = capp.api_pools_join(
            PoolJoinRequest(student_id=sid, course_code=course)
        )
        assert joined["status"] == "ok"

    pool = capp.api_pools(course_code=course)
    assert pool["waiting_count"] == 5 and pool["ready_to_match"]
    assert set(pool["student_codes"]) == set(STUDENT_IDS)
    assert '"availability":' not in json.dumps(pool)

    result = capp.api_pools_match(PoolMatchRequest(course_code=course))
    assert result["status"] == "ok"
    assert len(result["groups"]) >= 1
    g = result["groups"][0]
    assert g["scheduled_slot"] is not None
    assert set(g["member_ids"]) == set(STUDENT_IDS)

    groups = capp.api_groups(student_id="s0")["groups"]
    assert len(groups) == 1
    assert groups[0]["course_code"] == course
    assert "member_ids" not in groups[0]

    mine = mapp.api_my_groups("s0")
    assert mine["profile_exists"] and mine["groups"]

    pool_after = capp.api_pools(course_code=course)
    assert pool_after["waiting_count"] == 0


def test_match_too_small(product_env) -> None:
    capp, mapp = product_env
    from standing.coordinator.app import (
        AuthRegisterRequest,
        PoolJoinRequest,
        PoolMatchRequest,
    )

    capp.api_auth_register(AuthRegisterRequest(student_code="a1", display_name="A"))
    _intake(mapp, "a1", "A", "MATH151", "1" * 224)
    capp.api_pools_join(PoolJoinRequest(student_id="a1", course_code="MATH151"))
    out = capp.api_pools_match(PoolMatchRequest(course_code="MATH151"))
    assert out["status"] == "too_small" and out["pool_size"] == 1


def test_pool_migration_present(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    apply_coordinator_migrations(db)
    with connect(db) as conn:
        tables = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "course_pool" in tables
        assert "availability" not in table_columns(conn, "students")
        assert "availability" not in table_columns(conn, "course_pool")
