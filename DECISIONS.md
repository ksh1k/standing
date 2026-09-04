# Design decisions

Unspecified choices recorded here so later phases stay consistent.

## Campus zones (fixed enum)

Public places only (constraint 2 / 5). Invented small fixed list:

| Enum value           | Meaning              |
|----------------------|----------------------|
| `west_campus`        | West campus area     |
| `east_campus`        | East campus area     |
| `main_library`       | Main library         |
| `student_center`     | Student center       |
| `engineering_quad`   | Engineering quad     |

No residential locations are ever valid zone values.

## Slot grid

- Days: Monday–Sunday (indices 0–6)
- Hours: 07:00–23:00 local, 30-minute slots → 32 slots/day, 224/week (indices 0–223)
- Meeting length: 3 consecutive slots (90 minutes)
- Meetings must not cross a day boundary → 30 legal starts/day × 7 = 210 legal meeting starts/week
- Constants live in `standing/constants.py`
- **`start_slot` in negotiation messages is a week-bitmap index (0–223)** that satisfies `is_legal_meeting_start`, not a 0–209 dense index.

## Availability encoding

- Member DB column `student_profile.availability` is `TEXT NOT NULL`
- Wire/storage codec: 224-character string of `0`/`1` (`1` = free)
- Coordinator DB has **no** availability column (enforced by tests)

## Courses storage

- Stored as JSON text arrays in SQLite (`courses TEXT`)
- Normalized with `normalize_course_code`: uppercase + whitespace stripped

## Preferred zones / time-of-day

- `preferred_zones`: JSON text array of `CampusZone` values
- `time_of_day_preference`: JSON object with keys `morning`, `afternoon`, `evening` (floats); member DB only

### ToD buckets for scoring (Phase 2)

Slot-in-day index on the 07:00–23:00 grid:

| Bucket      | Slot-in-day | Clock (start)   |
|-------------|-------------|-----------------|
| morning     | 0–9         | 07:00–11:30     |
| afternoon   | 10–19       | 12:00–16:30     |
| evening     | 20–29       | 17:00–22:30     |

## Dual databases

- **Member DB:** full profile (incl. `display_name`, `availability`, `time_of_day_preference`) + private `attendance` table
- **Coordinator DB:** `students` (no availability, no display_name), `groups`, `sessions` (no per-member attended columns), plus Phase 2 negotiation tables
- Separate SQLite files; applied via `standing.db.apply_*_migrations`

## FastAPI

- Coordinator: `GET /healthz` only. Negotiation is **in-process** (`NegotiateSession`) so availability never enters coordinator HTTP handlers.
- Member: `GET /healthz`, optional `POST /availability` + `POST /evaluate` for local demo (bitmap stays in the member process).
- Bind intent: `--host 127.0.0.1` (constraint 6)

## Group defaults

- `preferred_group_size` CHECK between 4 and 6 (constraint 5)
- Group `status`: `forming` | `active` | `disbanded`
- `scheduled_slot` on `groups` is nullable until a slot is agreed (later phases)

## Sessions vs attendance

- Coordinator `sessions`: `session_id`, `group_id`, `scheduled_datetime`, `location` only
- Individual attendance lives only in member `attendance` (constraint 4)
- Group-level aggregates may be derived later without exposing per-member rows to peers

## Phase 2 — Negotiation

### Message types (JSONL log)

Each line is one JSON object with `type`, `group_id`, `ts` (UTC ISO), plus:

| type      | fields |
|-----------|--------|
| PROPOSE   | `start_slot` |
| RESPOND   | `start_slot`, `verdict: {kind, delta?}` — **no `student_id`** |
| CONFIRM   | `start_slot` |
| WITHDRAW  | `reason`, optional `student_id` |

Log path is configurable (`NegotiationLog`); tests use a tmp path.

### Verdicts

- `accept` | `reject` | `accept_if_shifted` with `delta ∈ {-2,-1,+1,+2}`
- Member `evaluate` tries shifts in order `-1, +1, -2, +2` (nearer first)

### Scoring / search

- Candidate set = all 210 legal starts
- **Base score** = mean of members’ ToD weights for that slot’s bucket
- **Shift-hint bonus** = `+1.0` per `accept_if_shifted` pointing at that slot (cumulative within a session)
- Propose highest score; tie-break **lower `start_slot`**
- Unanimous `accept` → CONFIRM and stop
- Otherwise mark candidate rejected, apply shift hints, continue
- **Budget** = 40 proposal rounds (`PROPOSAL_BUDGET`)
- On exhaustion: return best partial (`start_slot` with max `accept_count`); **never** CONFIRM a slot any member rejected

### Aggregate ToD preference

Coordinator receives ToD **weights only** (not bitmaps) to score candidates. Bitmaps stay inside `InProcessMember` / member agent stores.

### Persistence (leakage-safe)

Migration `002_coordinator.sql`:

- `negotiation_candidates(negotiation_id, slot, accept_count, status, score)` — aggregate counts only
- `negotiation_rounds(...)` — per-round meta (`proposed_slot`, `accept_count`, `outcome`)
- **No** per-member per-candidate verdict table after round resolution
- Ephemeral in-memory per-round responses discarded after aggregating `accept_count`

### Five-student fixture

- `tests/fixtures/five_students.py`
- **Expected unanimous slot = 78** (Wednesday 14:00)
- Documented decoys force search (not first-pick)

## Dependencies

- Only: FastAPI, uvicorn, pytest, icalendar (+ their transitive deps from pip)
- SQLite via stdlib `sqlite3`
- No ORM, Docker, React, or cloud SDKs

## Local-only git

- Repository initialized at `/workspace/standing`
- No remote push; no `git config` changes by automation
