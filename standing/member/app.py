"""Member agent FastAPI — healthz, evaluate, intake, my-groups, notifications."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from standing.constants import SLOTS_PER_WEEK, CampusZone, StudyStyle, YearLevel
from standing.db import apply_coordinator_migrations, apply_member_migrations, connect
from standing.models import normalize_course_code
from standing.negotiation.member_eval import evaluate

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("STANDING_DATA_DIR", str(REPO_ROOT / "data")))
MEMBER_DB = Path(os.environ.get("STANDING_MEMBER_DB", str(DATA_DIR / "member.db")))
COORD_DB = Path(os.environ.get("STANDING_COORD_DB", str(DATA_DIR / "coordinator.db")))

_LOCAL_AVAILABILITY: str | None = None


def _ensure_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    apply_member_migrations(MEMBER_DB)


def _ensure_coord_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    apply_coordinator_migrations(COORD_DB)


def _sync_public_to_coordinator(
    *,
    student_id: str,
    year: YearLevel,
    courses: list[str],
    preferred_group_size: int,
    preferred_zones: list[CampusZone],
    study_style: StudyStyle,
) -> None:
    """Upsert coordinator students row — public fields only (no availability)."""
    _ensure_coord_db()
    with connect(COORD_DB) as conn:
        conn.execute(
            """
            INSERT INTO students (
                student_id, year, courses, preferred_group_size,
                preferred_zones, study_style
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                year=excluded.year,
                courses=excluded.courses,
                preferred_group_size=excluded.preferred_group_size,
                preferred_zones=excluded.preferred_zones,
                study_style=excluded.study_style
            """,
            (
                student_id,
                year.value,
                json.dumps(courses),
                preferred_group_size,
                json.dumps([z.value for z in preferred_zones]),
                study_style.value,
            ),
        )
        conn.commit()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _ensure_db()
    yield


app = FastAPI(title="Standing Member Agent", version="0.8.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "member"}


class SetAvailabilityRequest(BaseModel):
    availability: str = Field(..., min_length=224, max_length=224)


class EvaluateRequest(BaseModel):
    start_slot: int
    availability: str | None = Field(default=None, min_length=224, max_length=224)


@app.post("/availability")
def set_availability(body: SetAvailabilityRequest) -> dict[str, str]:
    global _LOCAL_AVAILABILITY
    _LOCAL_AVAILABILITY = body.availability
    return {"status": "ok"}


@app.post("/evaluate")
def evaluate_slot(body: EvaluateRequest) -> dict[str, Any]:
    bitmap = body.availability if body.availability is not None else _LOCAL_AVAILABILITY
    if bitmap is None:
        return {"error": "no availability set"}
    return {"verdict": evaluate(body.start_slot, bitmap).as_dict()}


class IntakeRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=120)
    year: YearLevel
    courses: list[str] = Field(default_factory=list)
    preferred_group_size: int = Field(default=5, ge=4, le=6)
    preferred_zones: list[CampusZone] = Field(default_factory=list)
    study_style: StudyStyle = StudyStyle.DISCUSSION
    time_of_day_preference: dict[str, float] = Field(
        default_factory=lambda: {"morning": 1.0, "afternoon": 1.0, "evening": 1.0}
    )
    availability: str | None = Field(default=None, min_length=224, max_length=224)


@app.post("/api/intake")
def api_intake(body: IntakeRequest) -> dict[str, Any]:
    _ensure_db()
    courses = [normalize_course_code(c) for c in body.courses if c.strip()]
    avail = body.availability or ("1" * SLOTS_PER_WEEK)
    with connect(MEMBER_DB) as conn:
        conn.execute(
            """
            INSERT INTO student_profile (
                student_id, display_name, year, courses, availability,
                preferred_group_size, preferred_zones, study_style,
                time_of_day_preference, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(student_id) DO UPDATE SET
                display_name=excluded.display_name, year=excluded.year,
                courses=excluded.courses, availability=excluded.availability,
                preferred_group_size=excluded.preferred_group_size,
                preferred_zones=excluded.preferred_zones,
                study_style=excluded.study_style,
                time_of_day_preference=excluded.time_of_day_preference,
                updated_at=datetime('now')
            """,
            (
                body.student_id, body.display_name, body.year.value, json.dumps(courses),
                avail, body.preferred_group_size, json.dumps([z.value for z in body.preferred_zones]),
                body.study_style.value, json.dumps(body.time_of_day_preference),
            ),
        )
        conn.commit()
    _sync_public_to_coordinator(
        student_id=body.student_id,
        year=body.year,
        courses=courses,
        preferred_group_size=body.preferred_group_size,
        preferred_zones=body.preferred_zones,
        study_style=body.study_style,
    )
    return {"status": "ok", "student_id": body.student_id}


@app.get("/api/intake/{student_id}")
def api_get_intake(student_id: str) -> dict[str, Any]:
    _ensure_db()
    with connect(MEMBER_DB) as conn:
        row = conn.execute(
            "SELECT * FROM student_profile WHERE student_id = ?", (student_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "profile not found")
    return {
        "student_id": row["student_id"],
        "display_name": row["display_name"],
        "year": row["year"],
        "courses": json.loads(row["courses"]),
        "preferred_group_size": row["preferred_group_size"],
        "preferred_zones": json.loads(row["preferred_zones"]),
        "study_style": row["study_style"],
        "time_of_day_preference": json.loads(row["time_of_day_preference"]),
        "has_availability": bool(row["availability"]),
    }


@app.get("/api/groups")
def api_my_groups(student_id: str) -> dict[str, Any]:
    """Sessions for this student: time + public place only."""
    _ensure_db()
    suffix = f"-{student_id}"
    with connect(MEMBER_DB) as conn:
        prof = conn.execute(
            "SELECT 1 FROM student_profile WHERE student_id = ?", (student_id,)
        ).fetchone()
        rows = [
            r
            for r in conn.execute(
                "SELECT session_id, group_id, scheduled_datetime, location "
                "FROM local_sessions ORDER BY scheduled_datetime"
            )
            if r["session_id"].endswith(suffix)
        ]
    groups: dict[str, dict[str, Any]] = {}
    for r in rows:
        gid = r["group_id"] or r["session_id"]
        groups.setdefault(gid, {"group_id": gid, "sessions": []})
        groups[gid]["sessions"].append(
            {
                "session_id": r["session_id"],
                "scheduled_datetime": r["scheduled_datetime"],
                "location": r["location"],
            }
        )
    return {"student_id": student_id, "profile_exists": prof is not None, "groups": list(groups.values())}


@app.get("/api/notifications")
def api_notifications(student_id: str) -> dict[str, Any]:
    _ensure_db()
    with connect(MEMBER_DB) as conn:
        rows = conn.execute(
            "SELECT notification_id, kind, body, session_id, created_at FROM notifications "
            "WHERE student_id = ? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()
    return {
        "student_id": student_id,
        "notifications": [dict(r) for r in rows],
    }
