# Standing

Local study-group coordination for campus peers. Phase 1: repository scaffold, data model, SQL migrations, empty FastAPI stubs, and structural tests.

Enrollment data is self-reported or synthetic. Everything is designed to run on localhost only.

## Hard constraints

1. No real university systems. Do not attempt to access, log into, scrape, or automate any tamu.edu domain or any university portal, registration system, or learning management system. Do not request my university credentials. All enrollment data in this project is self-reported by the user or synthetic.
2. No residence data. Never collect, store, or process a student's address, dorm, apartment, or building of residence. Location preference is expressed only as a coarse public campus zone chosen from a fixed list, for example "west campus" or "main library". If you find yourself adding a home location field, stop and ask me.
3. Schedules never cross the boundary. A student's availability bitmap lives only in their own agent's store. No other agent, including the coordinator, may request, receive, or persist another student's full bitmap. The coordinator learns only accept/reject answers to specific proposed slots, and nothing else.
4. Attendance is private. Individual attendance records are visible only to that student and are never shown to other group members. Group-level aggregate statistics are fine.
5. Group meetings only, in public places. The system never proposes a one-on-one first meeting and never proposes any location that is residential. Default group size is 4 to 6.
6. Everything runs locally. All services bind to localhost. Do not deploy anything publicly, send real email, or post to any external service without asking me first.

## Stack

- Python 3.11+
- SQLite (stdlib)
- FastAPI + uvicorn
- pytest
- icalendar
- stdlib only beyond the above (no React, Docker, ORM, or cloud services)

## Layout

```
standing/
  README.md
  DECISIONS.md
  requirements.txt
  standing/
    __init__.py
    constants.py      # slot grid (224), zones, enums
    models.py         # dataclasses / helpers (no I/O)
    db.py             # migration apply helpers
    migrations/
      001_member.sql
      001_coordinator.sql
    coordinator/app.py   # /healthz stub
    member/app.py        # /healthz stub
  static/             # reserved for Phase 6 UI
  tests/
```

## Setup

```bash
cd /workspace/standing
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run stubs (localhost only)

```bash
source .venv/bin/activate
uvicorn standing.coordinator.app:app --host 127.0.0.1 --port 8000
uvicorn standing.member.app:app --host 127.0.0.1 --port 8001
```

## Tests

```bash
source .venv/bin/activate
pytest -v
```

## Phase 1 scope

- Repo, dependencies, data model, SQL migrations
- Empty FastAPI `/healthz` stubs
- Minimal pytest suite that passes
- README (these constraints) + DECISIONS.md
- One git commit

**Out of scope for Phase 1:** negotiation, group formation, UI, persistence application logic beyond migrations.
