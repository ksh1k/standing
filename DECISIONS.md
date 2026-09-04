# Design decisions (Phase 1)

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

## Availability encoding

- Member DB column `student_profile.availability` is `TEXT NOT NULL`
- Phase 1 does not prescribe a wire codec beyond “224-slot bitmap”; a simple 224-character string of `0`/`1` is assumed for later phases
- Coordinator DB has **no** availability column (enforced by tests)

## Courses storage

- Stored as JSON text arrays in SQLite (`courses TEXT`)
- Normalized with `normalize_course_code`: uppercase + whitespace stripped

## Preferred zones / time-of-day

- `preferred_zones`: JSON text array of `CampusZone` values
- `time_of_day_preference`: JSON object with keys `morning`, `afternoon`, `evening` (floats); member DB only

## Dual databases

- **Member DB:** full profile (incl. `display_name`, `availability`, `time_of_day_preference`) + private `attendance` table
- **Coordinator DB:** `students` (no availability, no display_name), `groups`, `sessions` (no per-member attended columns)
- Separate SQLite files; applied via `standing.db.apply_*_migrations`

## FastAPI stubs

- Phase 1 exposes only `GET /healthz` on coordinator and member apps
- Bind intent documented as `--host 127.0.0.1` (constraint 6)
- No negotiation / formation / persistence APIs yet

## Group defaults

- `preferred_group_size` CHECK between 4 and 6 (constraint 5)
- Group `status`: `forming` | `active` | `disbanded`
- `scheduled_slot` on `groups` is nullable until a slot is agreed (later phases)

## Sessions vs attendance

- Coordinator `sessions`: `session_id`, `group_id`, `scheduled_datetime`, `location` only
- Individual attendance lives only in member `attendance` (constraint 4)
- Group-level aggregates may be derived later without exposing per-member rows to peers

## Dependencies

- Only: FastAPI, uvicorn, pytest, icalendar (+ their transitive deps from pip)
- SQLite via stdlib `sqlite3`
- Phase 1 smoke tests import apps directly (no TestClient)
- No ORM, Docker, React, or cloud SDKs

## Local-only git

- Repository initialized at `/workspace/standing`
- No remote push; no `git config` changes by automation
