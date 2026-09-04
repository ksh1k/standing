# Standing

Local study-group coordination for campus peers. Phase 1 scaffold + Phase 2 negotiation protocol (member evaluate + coordinator search, leakage-safe state).

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
    constants.py
    models.py
    db.py
    migrations/
      001_member.sql
      001_coordinator.sql
      002_coordinator.sql   # negotiation_candidates / negotiation_rounds
    negotiation/            # Phase 2 protocol
    coordinator/app.py
    member/app.py
  tests/
    fixtures/five_students.py
  static/                   # reserved for later UI
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

Phase 2 negotiation is exercised in-process via `NegotiateSession` (see `tests/test_negotiation.py` and `tests/fixtures/five_students.py`). Expected unanimous fixture slot: **78** (Wed 14:00).

## Phase status

- **Phase 1:** repo, dual SQLite schemas, slot grid, `/healthz` stubs, structural tests
- **Phase 2:** message types, member `evaluate`, coordinator search (40-round budget), JSONL log, leakage tests, 5-student fixture proof

**Out of scope still:** group formation UI, production messaging transport, Phase 3+.
