# Design decisions

Unspecified choices recorded here for later-phase consistency.

## Campus zones (fixed enum)

Public places only (constraints 2 / 5): `west_campus`, `east_campus`, `main_library`, `student_center`, `engineering_quad`. Never residential.

## Slot grid

- Days Mon–Sun (0–6); hours 07:00–23:00 local; 30-min slots → 32/day, 224/week (0–223)
- Meeting = 3 consecutive slots (90 min); no day-boundary cross → 30 legal starts/day × 7 = 210
- Constants in `standing/constants.py`
- Negotiation `start_slot` is a week-bitmap index (0–223) with `is_legal_meeting_start`

## Availability / courses / prefs

- Member `student_profile.availability`: 224-char `0`/`1` string (`1` = free). Coordinator has **no** availability column.
- Courses: JSON text arrays; `normalize_course_code` = uppercase + strip whitespace
- `preferred_zones`: JSON `CampusZone` array; `time_of_day_preference`: `{morning,afternoon,evening}` floats (member only)
- ToD buckets (slot-in-day): morning 0–9, afternoon 10–19, evening 20–29

## Dual databases

- **Member:** full profile (`display_name`, availability, ToD) + private `attendance`
- **Coordinator:** `students` (no availability / display_name), `groups`, `sessions` (no per-member attended), Phase 2 negotiation tables
- Separate SQLite files via `standing.db.apply_*_migrations`

## FastAPI / group defaults

- Coordinator: `GET /healthz` only; negotiation in-process (`NegotiateSession`) so bitmaps never hit coordinator HTTP
- Member: `GET /healthz`, optional `POST /availability` + `POST /evaluate` (local demo)
- Bind `--host 127.0.0.1` (constraint 6)
- `preferred_group_size` CHECK 4–6; group status `forming|active|disbanded`; `scheduled_slot` nullable until agreed
- Attendance only in member DB (constraint 4)

## Phase 2 — Negotiation

| type | fields |
|------|--------|
| PROPOSE | `start_slot` |
| RESPOND | `start_slot`, `verdict: {kind, delta?}` — **no `student_id`** |
| CONFIRM | `start_slot` |
| WITHDRAW | `reason`, optional `student_id` |

- Verdicts: `accept` | `reject` | `accept_if_shifted` (`delta ∈ {-2,-1,+1,+2}`); member tries shifts `-1,+1,-2,+2`
- Score = mean ToD weight for slot bucket + `+1.0` per shift hint; propose max score, tie-break lower slot
- Unanimous accept → CONFIRM; else reject candidate, apply hints; budget `PROPOSAL_BUDGET=40`
- Exhaustion → best partial (`accept_count`); never CONFIRM a rejected slot
- Coordinator gets ToD weights only; bitmaps stay in `InProcessMember`
- Persist (`002_coordinator.sql`): `negotiation_candidates` / `negotiation_rounds` aggregates only — no per-member verdict table
- Fixture `tests/fixtures/five_students.py`: expected unanimous slot **78** (Wed 14:00)

## Phase 3 — Group formation

1. **Greedy** (`greedy.py`): pack sizes via `best_pack_sizes` [4,6]; courses by descending eligible count; soft fill + `student_id` tie-break
2. **Local search** (`local_search.py`): swap / reassign / form-from-unplaced; accept strict objective increases; seed `42`, iters `200`
3. **Negotiate gate** (`pipeline.py`): emit only CONFIRM groups. Soft score never reads bitmaps.

Objective: `W_PLACE=1e6` × placed + Σ groups (`W_STYLE=1e3`·style + `W_YEAR=10`·year + `W_ZONE=1`·zones). Soft scoring uses `FormationStudent` (no availability). Stubs `always_confirm_stub` / `never_confirm_stub` for combinatorial unit tests only.

## Phase 4 — Synthetic population + simulation

- Seed: `SYNTHETIC_SEED = 20260903` (fixed); 300 students × 12 courses
- Courses: `CSCE121`, `CSCE221`, `CSCE314`, `CSCE315`, `MATH151`, `MATH152`, `MATH304`, `PHYS206`, `PHYS207`, `ENGL104`, `STAT211`, `ECEN214`
- Availability model: each course has a class block (busy) + a primary shared evening/weekend free window for most enrollees; per-student evening/weekend jitter and a minority with conflicting free windows so some groups fail negotiation
- Bitmaps only on member side during sim negotiation; no residence fields
- Artifacts: `data/synthetic_students.json`, `data/simulation_stats.json`, `SIMULATION_REPORT.md`


## Phase 5 — Persistence behaviors

- **Line budget:** raised from ~3000 to **~4500** (user-approved 2026-09-03).
- **Clock:** injectible `FrozenClock` / explicit `now: datetime` on every check — never real `sleep` (time-travel tests).
- **Notification model:** member DB `notifications` table only (`reminder` | `dormancy_checkin`); local store — no email/external. Deduped by `(student_id, kind, session_id)`. Member also keeps `local_sessions` for schedule+place.
- **Weekly reminder:** fires when `session_dt - 24h <= now < session_dt` (not earlier).
- **Dormancy:** trailing **3** consecutive misses (ordered by `local_sessions.scheduled_datetime`) → private `dormancy_checkin` to that student only. No group announce; no removal.
- **Active member:** listed in the group and **not** dormant (fewer than 3 trailing consecutive misses). Used by membership repair.
- **Aggregates:** coordinator `session_aggregates(session_id, attended_count, member_total)` only — no per-student attended flags on coordinator. Individual attendance stays in member `attendance`.
- **Drift:** if aggregate ratio `< 0.5` for **3 consecutive regular** sessions → reopen Phase 2 `NegotiateSession` with member-held bitmaps; record `drift_events`; on CONFIRM update `groups.scheduled_slot`.
- **Exam season:** manual `exam_dates(course_code, exam_date)`; window `[exam-14d, exam)`; add one `exam_season` second session (+3 days from primary); delete those sessions after window.
- **Repair:** if active members `< 4`, insert/update `merge_flags` for same-course merge (**flag only** — no merger UI).

## Dependencies / git

- Only FastAPI, uvicorn, pytest, icalendar (+ transitive); SQLite via stdlib; no ORM/Docker/React/cloud
- Repo at `/workspace/standing`; no remote push; no automation `git config` changes

## Phase 6 — Web UI + ICS

- **UI:** `static/` plain HTML+JS; coordinator `StaticFiles`. Poll `/api/transcript?after=N` every **1000 ms**.
- **Live transcript:** `POST /api/demo/negotiate` runs five-student fixture; appends PROPOSE/RESPOND/CONFIRM to `data/negotiation_log.jsonl` (no bitmaps; no `student_id` on RESPOND).
- **ICS:** SUMMARY, LOCATION (public zone), DTSTART/DTEND (90 min), optional UID. Slot→time: week Monday `2026-09-07` as UTC demo (`calendar_ics.py`).
- **Intake / my groups:** member `/api/intake`, `/api/groups?student_id=` via `local_sessions` (time+place only). Bind `127.0.0.1`; member CORS for `:8000`.
