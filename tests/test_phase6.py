"""Phase 6: ICS + API smoke (handlers directly; no httpx)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from icalendar import Calendar

from standing.calendar_ics import (
    DEFAULT_WEEK_MONDAY,
    build_group_ics,
    ics_from_slot,
    slot_label,
    slot_start_datetime,
)
from standing.constants import CampusZone, MEETING_DURATION_SLOTS, SLOT_MINUTES, StudyStyle, YearLevel


def _vevent(raw: bytes):
    return next(c for c in Calendar.from_ical(raw).walk() if c.name == "VEVENT")


def test_ics_generation() -> None:
    start = slot_start_datetime(78)
    raw = build_group_ics(
        title="Standing study group — CSCE315",
        location=CampusZone.MAIN_LIBRARY.value,
        start=start,
        uid="demo@standing.local",
    )
    ev = _vevent(raw)
    assert str(ev.get("summary")).startswith("Standing")
    assert str(ev.get("location")) == "main_library"
    assert ev.decoded("dtstart") == start
    assert b"ATTENDEE" not in raw
    raw2 = ics_from_slot(title="t", location="student_center", start_slot=78, uid="x")
    ev2 = _vevent(raw2)
    assert ev2.decoded("dtstart") == slot_start_datetime(78, DEFAULT_WEEK_MONDAY)
    assert (ev2.decoded("dtend") - ev2.decoded("dtstart")).total_seconds() == (
        MEETING_DURATION_SLOTS * SLOT_MINUTES * 60
    )
    assert "wednesday" in slot_label(78) and "14:00" in slot_label(78)


@pytest.fixture()
def coord_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "data"
    data.mkdir()
    import standing.coordinator.app as capp

    for k, v in {
        "DATA_DIR": data,
        "COORD_DB": data / "coordinator.db",
        "MEMBER_DB": data / "member.db",
        "LOG_PATH": data / "negotiation_log.jsonl",
    }.items():
        monkeypatch.setattr(capp, k, v)
    capp._ensure_coord_db()
    with capp._demo_lock:
        capp._demo_status.update(running=False, last=None)
    return capp


@pytest.fixture()
def member_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "mdata"
    data.mkdir()
    import standing.member.app as mapp

    monkeypatch.setattr(mapp, "DATA_DIR", data)
    monkeypatch.setattr(mapp, "MEMBER_DB", data / "member.db")
    monkeypatch.setattr(mapp, "COORD_DB", data / "coordinator.db")
    mapp._ensure_db()
    return mapp


def test_static_files_exist() -> None:
    root = Path(__file__).resolve().parents[1] / "static"
    for name in ("index.html", "intake.html", "join.html", "groups.html", "dashboard.html", "app.js", "style.css"):
        assert (root / name).is_file(), name


def test_api_groups_transcript_demo_ics(coord_env, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin demo slot — live demo randomizes; tests need a reliable confirm.
    from tests.fixtures.five_students import EXPECTED_UNANIMOUS_SLOT
    monkeypatch.setattr("random.choice", lambda _pool: EXPECTED_UNANIMOUS_SLOT)
    assert coord_env.api_transcript()["total"] == 0
    assert coord_env.api_groups()["groups"] == []
    payload = coord_env.api_demo_negotiate(background=False)
    assert payload["status"] == "confirmed"
    assert payload["start_slot"] == payload["expected_slot"]
    assert payload["start_slot"] is not None
    types = {ln.get("type") for ln in coord_env.api_transcript()["lines"]}
    assert {"PROPOSE", "RESPOND", "CONFIRM"} <= types
    for ln in coord_env.api_transcript()["lines"]:
        if ln.get("type") == "RESPOND":
            assert "student_id" not in ln
    g = coord_env.api_groups()["groups"][0]
    assert g["scheduled_slot"] == payload["start_slot"] and g["zone"] == "main_library" and "member_ids" not in g
    ics = coord_env.api_ics(g["group_id"])
    assert ics.media_type == "text/calendar" and b"LOCATION:main_library" in ics.body
    assert len(coord_env.api_groups(student_id="s0")["groups"]) == 1
    assert coord_env.api_groups(student_id="nobody")["groups"] == []
    assert coord_env.healthz()["service"] == "coordinator"


def test_api_intake_and_my_groups(member_env, coord_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import standing.member.app as mapp
    from standing.member.app import IntakeRequest
    from tests.fixtures.five_students import EXPECTED_UNANIMOUS_SLOT

    monkeypatch.setattr("random.choice", lambda _pool: EXPECTED_UNANIMOUS_SLOT)
    mapp.MEMBER_DB, mapp.DATA_DIR, mapp.COORD_DB = (
        coord_env.MEMBER_DB, coord_env.DATA_DIR, coord_env.COORD_DB
    )
    mapp._ensure_db()
    body = IntakeRequest(
        student_id="s0",
        display_name="Alex",
        year=YearLevel.JUNIOR,
        courses=["CSCE315"],
        preferred_zones=[CampusZone.MAIN_LIBRARY],
        study_style=StudyStyle.DISCUSSION,
    )
    assert mapp.api_intake(body)["status"] == "ok"
    assert mapp.api_get_intake("s0")["display_name"] == "Alex"
    assert "availability" not in mapp.api_get_intake("s0")
    with pytest.raises(HTTPException):
        mapp.api_get_intake("missing")
    coord_env.api_demo_negotiate(background=False)
    groups = mapp.api_my_groups("s0")
    assert groups["profile_exists"] and groups["groups"]
    assert "location" in groups["groups"][0]["sessions"][0]
    assert mapp.api_notifications("s0")["notifications"] == []
    assert mapp.healthz()["service"] == "member"
