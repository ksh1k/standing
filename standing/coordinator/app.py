"""Coordinator FastAPI — transcript, groups, demo negotiate, static UI (localhost)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from standing.calendar_ics import ics_from_slot, slot_label, slot_start_datetime
from standing.constants import CampusZone
from standing.db import apply_coordinator_migrations, apply_member_migrations, connect
from standing.negotiation.coordinator_negotiate import NegotiateSession
from standing.negotiation.log import NegotiationLog

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "static"
DATA_DIR = Path(os.environ.get("STANDING_DATA_DIR", str(REPO_ROOT / "data")))
COORD_DB = Path(os.environ.get("STANDING_COORD_DB", str(DATA_DIR / "coordinator.db")))
MEMBER_DB = Path(os.environ.get("STANDING_MEMBER_DB", str(DATA_DIR / "member.db")))
LOG_PATH = Path(os.environ.get("STANDING_NEGOTIATION_LOG", str(DATA_DIR / "negotiation_log.jsonl")))

_demo_lock = threading.Lock()
_demo_status: dict[str, Any] = {"running": False, "last": None}


def _ensure_coord_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    apply_coordinator_migrations(COORD_DB)


def _ensure_member_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    apply_member_migrations(MEMBER_DB)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _ensure_coord_db()
    yield


app = FastAPI(title="Standing Coordinator", version="0.7.0", lifespan=_lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "coordinator"}


@app.get("/api/transcript")
def api_transcript(after: int = 0, limit: int = 500) -> dict[str, Any]:
    after, limit = max(0, int(after)), min(max(1, int(limit)), 5000)
    rows = NegotiationLog(LOG_PATH).read_all()
    return {"total": len(rows), "after": after, "lines": rows[after : after + limit]}


@app.get("/api/groups")
def api_groups(student_id: str | None = None) -> dict[str, Any]:
    """Time + public zone only; never attendance or private schedules."""
    _ensure_coord_db()
    out: list[dict[str, Any]] = []
    with connect(COORD_DB) as conn:
        for g in conn.execute(
            "SELECT group_id, course_code, member_ids, scheduled_slot, zone, status "
            "FROM groups ORDER BY created_at DESC"
        ):
            members = json.loads(g["member_ids"] or "[]")
            if student_id and student_id not in members:
                continue
            slot = g["scheduled_slot"]
            sessions = conn.execute(
                "SELECT session_id, scheduled_datetime, location FROM sessions "
                "WHERE group_id = ? ORDER BY scheduled_datetime",
                (g["group_id"],),
            ).fetchall()
            out.append(
                {
                    "group_id": g["group_id"],
                    "course_code": g["course_code"],
                    "scheduled_slot": slot,
                    "slot_label": slot_label(slot) if slot is not None else None,
                    "zone": g["zone"],
                    "status": g["status"],
                    "member_count": len(members),
                    "sessions": [dict(s) for s in sessions],
                }
            )
    return {"groups": out}


@app.get("/api/ics/{group_id}")
def api_ics(group_id: str) -> Response:
    _ensure_coord_db()
    with connect(COORD_DB) as conn:
        g = conn.execute(
            "SELECT group_id, course_code, scheduled_slot, zone FROM groups WHERE group_id = ?",
            (group_id,),
        ).fetchone()
    if g is None:
        raise HTTPException(404, "group not found")
    if g["scheduled_slot"] is None:
        raise HTTPException(400, "group not scheduled")
    zone = g["zone"] or CampusZone.MAIN_LIBRARY.value
    raw = ics_from_slot(
        title=f"Standing study group — {g['course_code']}",
        location=zone,
        start_slot=int(g["scheduled_slot"]),
        uid=f"{group_id}@standing.local",
    )
    return Response(
        content=raw,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{group_id}.ics"'},
    )


def _persist_confirmed(
    *, group_id: str, course_code: str, member_ids: list[str], start_slot: int, zone: str
) -> str:
    _ensure_coord_db()
    _ensure_member_db()
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    dt_iso = slot_start_datetime(start_slot).isoformat()
    with connect(COORD_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO groups "
            "(group_id, course_code, member_ids, scheduled_slot, zone, status) "
            "VALUES (?, ?, ?, ?, ?, 'active')",
            (group_id, course_code, json.dumps(member_ids), start_slot, zone),
        )
        conn.execute(
            "INSERT OR REPLACE INTO sessions "
            "(session_id, group_id, scheduled_datetime, location) VALUES (?, ?, ?, ?)",
            (session_id, group_id, dt_iso, zone),
        )
        conn.commit()
    with connect(MEMBER_DB) as conn:
        for sid in member_ids:
            conn.execute(
                "INSERT OR REPLACE INTO local_sessions "
                "(session_id, group_id, scheduled_datetime, location) VALUES (?, ?, ?, ?)",
                (f"{session_id}-{sid}", group_id, dt_iso, zone),
            )
        conn.commit()
    return session_id


def _run_demo_negotiate() -> dict[str, Any]:
    import random

    from standing.constants import TimeOfDay, is_legal_meeting_start
    from standing.negotiation.search import all_legal_starts, time_of_day_for_slot
    from tests.fixtures.five_students import STUDENT_IDS, build_five_members

    # Random shared window each demo run (prefer weekday afternoon for a realistic look).
    legal = [s for s in all_legal_starts() if is_legal_meeting_start(s)]
    afternoon = [
        s
        for s in legal
        if time_of_day_for_slot(s) is TimeOfDay.AFTERNOON and (s // 32) < 5
    ]
    pool = afternoon or legal
    target_slot = random.choice(pool)

    _ensure_coord_db()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    members = build_five_members(unanimous_slot=target_slot)
    group_id = f"demo-{uuid.uuid4().hex[:8]}"
    zone = CampusZone.MAIN_LIBRARY.value
    result = NegotiateSession(
        group_id=group_id,
        members=members,
        member_tod=[m.tod for m in members],
        log=NegotiationLog(LOG_PATH),
        db_path=COORD_DB,
    ).run()
    session_id = None
    if result.status == "confirmed" and result.start_slot is not None:
        session_id = _persist_confirmed(
            group_id=group_id,
            course_code="CSCE315",
            member_ids=list(STUDENT_IDS),
            start_slot=result.start_slot,
            zone=zone,
        )
    return {
        "status": result.status,
        "start_slot": result.start_slot,
        "expected_slot": target_slot,
        "accept_count": result.accept_count,
        "rounds": result.rounds,
        "negotiation_id": result.negotiation_id,
        "group_id": group_id,
        "session_id": session_id,
        "zone": zone,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/demo/negotiate")
def api_demo_negotiate(background: bool = True) -> dict[str, Any]:
    with _demo_lock:
        if _demo_status["running"]:
            return {"status": "already_running", "last": _demo_status["last"]}
        _demo_status["running"] = True

    def _job() -> None:
        try:
            payload = _run_demo_negotiate()
            with _demo_lock:
                _demo_status["last"] = payload
        finally:
            with _demo_lock:
                _demo_status["running"] = False

    if background:
        threading.Thread(target=_job, daemon=True).start()
        return {"status": "started", "log_path": str(LOG_PATH)}
    payload = _run_demo_negotiate()
    with _demo_lock:
        _demo_status["last"] = payload
        _demo_status["running"] = False
    return payload


@app.get("/api/demo/status")
def api_demo_status() -> dict[str, Any]:
    with _demo_lock:
        return {"running": _demo_status["running"], "last": _demo_status["last"]}


# Same-origin member API for public tunnel / single-URL demos
from standing.member.app import app as member_app  # noqa: E402

app.mount("/member", member_app)

if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
