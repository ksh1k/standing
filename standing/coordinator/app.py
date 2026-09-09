"""Coordinator FastAPI — auth, pools, groups, demo negotiate, static UI."""

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
from pydantic import BaseModel, Field

from standing.calendar_ics import ics_from_slot, slot_label, slot_start_datetime
from standing.constants import SLOTS_PER_WEEK, CampusZone, StudyStyle, YearLevel
from standing.coordinator.pools import POOL_MATCH_MIN, run_course_match
from standing.db import apply_coordinator_migrations, apply_member_migrations, connect
from standing.models import normalize_course_code
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


app = FastAPI(title="Standing Coordinator", version="0.8.0", lifespan=_lifespan)


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".js", ".html", ".css")) or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


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



# --- Product MVP: identity + course wait pools (manual match) -----------------


class AuthRegisterRequest(BaseModel):
    student_id: str | None = Field(default=None, min_length=1, max_length=64)
    student_code: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=120)


class AuthLoginRequest(BaseModel):
    student_id: str | None = Field(default=None, min_length=1, max_length=64)
    student_code: str | None = Field(default=None, min_length=1, max_length=64)


class PoolJoinRequest(BaseModel):
    student_id: str | None = Field(default=None, min_length=1, max_length=64)
    student_code: str | None = Field(default=None, min_length=1, max_length=64)
    course_code: str = Field(..., min_length=1, max_length=32)


class PoolMatchRequest(BaseModel):
    course_code: str = Field(..., min_length=1, max_length=32)


def _student_id_from(body: BaseModel) -> str:
    data = body.model_dump()
    raw = (data.get("student_id") or data.get("student_code") or "").strip()
    if not raw:
        raise HTTPException(400, "student_id or student_code required")
    return raw


def _public_profile(student_id: str) -> dict[str, Any] | None:
    """Public profile — never raw availability bitmap."""
    _ensure_member_db()
    _ensure_coord_db()
    with connect(MEMBER_DB) as mconn:
        row = mconn.execute(
            "SELECT student_id, display_name, year, courses, preferred_group_size, "
            "preferred_zones, study_style, availability FROM student_profile "
            "WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    if row is None:
        with connect(COORD_DB) as cconn:
            crow = cconn.execute(
                "SELECT student_id, year, courses, preferred_group_size, "
                "preferred_zones, study_style FROM students WHERE student_id = ?",
                (student_id,),
            ).fetchone()
        if crow is None:
            return None
        courses = json.loads(crow["courses"] or "[]")
        return {
            "student_code": crow["student_id"],
            "student_id": crow["student_id"],
            "display_name": None,
            "year": crow["year"],
            "courses": courses,
            "preferred_group_size": crow["preferred_group_size"],
            "preferred_zones": json.loads(crow["preferred_zones"] or "[]"),
            "study_style": crow["study_style"],
            "has_availability": False,
            "profile_complete": bool(courses),
        }
    courses = json.loads(row["courses"] or "[]")
    return {
        "student_code": row["student_id"],
        "student_id": row["student_id"],
        "display_name": row["display_name"],
        "year": row["year"],
        "courses": courses,
        "preferred_group_size": row["preferred_group_size"],
        "preferred_zones": json.loads(row["preferred_zones"] or "[]"),
        "study_style": row["study_style"],
        "has_availability": bool(row["availability"]),
        "profile_complete": bool(courses) and bool(row["availability"]),
    }


@app.post("/api/auth/register")
def api_auth_register(body: AuthRegisterRequest) -> dict[str, Any]:
    """Create member stub + coordinator students row if new (no password)."""
    code = _student_id_from(body)
    name = body.display_name.strip()
    if not name:
        raise HTTPException(400, "display_name required")
    _ensure_coord_db()
    _ensure_member_db()
    created = False
    with connect(MEMBER_DB) as conn:
        if conn.execute(
            "SELECT 1 FROM student_profile WHERE student_id = ?", (code,)
        ).fetchone():
            conn.execute(
                "UPDATE student_profile SET display_name = ?, updated_at = datetime('now') "
                "WHERE student_id = ?",
                (name, code),
            )
            conn.commit()
        else:
            created = True
            conn.execute(
                """
                INSERT INTO student_profile (
                    student_id, display_name, year, courses, availability,
                    preferred_group_size, preferred_zones, study_style,
                    time_of_day_preference, updated_at
                ) VALUES (?, ?, ?, '[]', ?, 5, ?, ?, ?, datetime('now'))
                """,
                (
                    code,
                    name,
                    YearLevel.JUNIOR.value,
                    "1" * SLOTS_PER_WEEK,
                    json.dumps([CampusZone.MAIN_LIBRARY.value]),
                    StudyStyle.DISCUSSION.value,
                    json.dumps({"morning": 1.0, "afternoon": 1.0, "evening": 1.0}),
                ),
            )
            conn.commit()
    with connect(COORD_DB) as conn:
        if conn.execute("SELECT 1 FROM students WHERE student_id = ?", (code,)).fetchone() is None:
            created = True
            conn.execute(
                """
                INSERT INTO students (
                    student_id, year, courses, preferred_group_size,
                    preferred_zones, study_style
                ) VALUES (?, ?, '[]', 5, ?, ?)
                """,
                (
                    code,
                    YearLevel.JUNIOR.value,
                    json.dumps([CampusZone.MAIN_LIBRARY.value]),
                    StudyStyle.DISCUSSION.value,
                ),
            )
            conn.commit()
    profile = _public_profile(code)
    return {
        "status": "created" if created else "exists",
        "student_code": code,
        "student_id": code,
        "display_name": name,
        "profile": profile,
    }


@app.post("/api/auth/login")
def api_auth_login(body: AuthLoginRequest) -> dict[str, Any]:
    """Return public profile if student exists (no password)."""
    code = _student_id_from(body)
    profile = _public_profile(code)
    if profile is None:
        raise HTTPException(404, "profile not found")
    # Flat + nested for JS helpers
    return {"status": "ok", "profile": profile, **profile}


@app.post("/api/pools/join")
def api_pools_join(body: PoolJoinRequest) -> dict[str, Any]:
    """Add student to a course wait pool if profile is complete."""
    code = _student_id_from(body)
    course = normalize_course_code(body.course_code)
    if not course:
        raise HTTPException(400, "course_code required")
    _ensure_coord_db()
    _ensure_member_db()
    with connect(MEMBER_DB) as conn:
        row = conn.execute(
            "SELECT courses, availability FROM student_profile WHERE student_id = ?",
            (code,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "register and complete intake first")
    courses = json.loads(row["courses"] or "[]")
    if not courses or not row["availability"]:
        raise HTTPException(400, "profile incomplete: need courses and availability")
    if course not in courses:
        raise HTTPException(400, f"course {course} not in profile courses")
    with connect(COORD_DB) as conn:
        if conn.execute("SELECT 1 FROM students WHERE student_id = ?", (code,)).fetchone() is None:
            raise HTTPException(404, "coordinator student missing — re-run intake")
        existing = conn.execute(
            "SELECT status FROM course_pool WHERE course_code = ? AND student_id = ?",
            (course, code),
        ).fetchone()
        if existing and existing["status"] == "waiting":
            size = conn.execute(
                "SELECT COUNT(*) AS n FROM course_pool "
                "WHERE course_code = ? AND status = 'waiting'",
                (course,),
            ).fetchone()["n"]
            return {
                "status": "ok",
                "student_code": code,
                "student_id": code,
                "course_code": course,
                "pool_size": size,
                "waiting_count": size,
                "ready_to_match": size >= POOL_MATCH_MIN,
            }
        conn.execute(
            """
            INSERT INTO course_pool (course_code, student_id, status)
            VALUES (?, ?, 'waiting')
            ON CONFLICT(course_code, student_id) DO UPDATE SET
                status = 'waiting',
                joined_at = datetime('now')
            """,
            (course, code),
        )
        conn.commit()
        size = conn.execute(
            "SELECT COUNT(*) AS n FROM course_pool "
            "WHERE course_code = ? AND status = 'waiting'",
            (course,),
        ).fetchone()["n"]
    return {
        "status": "ok",
        "student_code": code,
        "student_id": code,
        "course_code": course,
        "pool_size": size,
        "waiting_count": size,
        "ready_to_match": size >= POOL_MATCH_MIN,
    }


@app.get("/api/pools")
def api_pools(course_code: str) -> dict[str, Any]:
    """Waiting count + public member codes (no availability)."""
    course = normalize_course_code(course_code)
    _ensure_coord_db()
    members: list[dict[str, Any]] = []
    with connect(COORD_DB) as conn:
        rows = conn.execute(
            """
            SELECT s.student_id, s.year, s.preferred_group_size, s.study_style, p.joined_at
            FROM course_pool p
            JOIN students s ON s.student_id = p.student_id
            WHERE p.course_code = ? AND p.status = 'waiting'
            ORDER BY p.joined_at, s.student_id
            """,
            (course,),
        ).fetchall()
        for r in rows:
            members.append(
                {
                    "student_id": r["student_id"],
                    "student_code": r["student_id"],
                    "year": r["year"],
                    "preferred_group_size": r["preferred_group_size"],
                    "study_style": r["study_style"],
                    "joined_at": r["joined_at"],
                }
            )
    codes = [m["student_id"] for m in members]
    return {
        "course_code": course,
        "pool_size": len(codes),
        "waiting_count": len(codes),
        "student_codes": codes,
        "min_match": POOL_MATCH_MIN,
        "ready_to_match": len(codes) >= POOL_MATCH_MIN,
        "members": members,
    }


# Back-compat alias used by older tests
api_pools_list = api_pools


@app.post("/api/pools/match")
def api_pools_match(body: PoolMatchRequest) -> dict[str, Any]:
    """Manual MVP trigger: formation + negotiation on a course wait pool."""
    course = normalize_course_code(body.course_code)
    _ensure_coord_db()
    _ensure_member_db()
    log_dir = DATA_DIR / "pool_match_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return run_course_match(
        coord_db=COORD_DB,
        member_db=MEMBER_DB,
        course_code=course,
        persist_confirmed=_persist_confirmed,
        log_dir=log_dir,
    )


# Same-origin member API for public tunnel / single-URL demos
from standing.member.app import app as member_app  # noqa: E402

app.mount("/member", member_app)

if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
