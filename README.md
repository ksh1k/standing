# Standing

Local study-group coordination for campus peers (Phases 1–6). Enrollment is self-reported or synthetic; everything binds to localhost.

## Hard constraints

1. No real university systems (no tamu.edu / portals / LMS; no university credentials).
2. No residence data — location prefs are coarse public campus zones only.
3. Availability bitmaps stay in the owning member agent; coordinator sees only accept/reject for proposed slots.
4. Individual attendance is private to that student.
5. Group meetings (size 4–6) in public places only — never 1:1 first meetings or residential locations.
6. Localhost only — no public deploy, email, or external posts without asking.

## Stack

Python 3.11+, SQLite (stdlib), FastAPI + uvicorn, pytest, icalendar. No React/Docker/ORM/cloud.

## Layout

```
standing/          # package: constants, models, db, migrations, negotiation, formation, persistence, calendar_ics
static/            # Phase 6 HTML/JS/CSS (no build)
seed_synthetic.py  # Phase 4: reproducible 300×12 population
run_simulation.py  # Phase 4: form + negotiate → report
data/              # synthetic JSON + negotiation_log.jsonl + local SQLite
tests/             # fixtures + constraint / negotiation / formation / synthetic / phase6 tests
SIMULATION_REPORT.md
```

## Setup

```bash
cd /workspace/standing && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run local UI (Phase 6 demo)

Two terminals, repo root, `.venv` active. Bind localhost only.

```bash
# Terminal A — coordinator + static UI + transcript / demo negotiate / .ics
cd /workspace/standing && source .venv/bin/activate
python -m standing.demo_server
# equivalent:
# uvicorn standing.coordinator.app:app --host 127.0.0.1 --port 8000

# Terminal B — member agent (intake + my groups + notifications)
cd /workspace/standing && source .venv/bin/activate
uvicorn standing.member.app:app --host 127.0.0.1 --port 8001
```

Open **http://127.0.0.1:8000/** — Intake, My groups, Coordinator dashboard.
On the dashboard click **Run 5-student demo negotiate**; transcript polls `/api/transcript` every 1s.


## Tests

```bash
source .venv/bin/activate && pytest -v
```

Phase 2 fixture slot: **78** (Wed 14:00). Phase 3: greedy → local search (seed 42, 200 iters) → negotiate gate.

## Phase 4–5

```bash
python seed_synthetic.py && python run_simulation.py   # or --subset 24
pytest -v tests/test_persistence.py                    # time-travel; local notifications only
```
## Phase status

- **1:** dual SQLite, slot grid, `/healthz`, structural tests
- **2:** propose/respond/confirm, member evaluate, 40-round search, leakage tests
- **3:** greedy + local search + CONFIRM-only emit
- **4:** synthetic 300×12 population + formation/negotiation simulation report
- **5:** persistence — reminders, dormancy, drift renegotiation, exam-season second session, merge flags
- **6:** plain HTML UI (intake / my groups / live transcript), `.ics`, demo negotiate endpoint
