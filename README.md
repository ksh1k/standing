# Standing

Local study-group coordination for campus peers (Phases 1–4). Enrollment is self-reported or synthetic; everything binds to localhost.

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
standing/          # package: constants, models, db, migrations, negotiation, formation
seed_synthetic.py  # Phase 4: reproducible 300×12 population
run_simulation.py  # Phase 4: form + negotiate → report
data/              # synthetic_students.json, simulation_stats.json
tests/             # fixtures + constraint / negotiation / formation / synthetic tests
SIMULATION_REPORT.md
```

## Setup

```bash
cd /workspace/standing && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run stubs

```bash
source .venv/bin/activate
uvicorn standing.coordinator.app:app --host 127.0.0.1 --port 8000
uvicorn standing.member.app:app --host 127.0.0.1 --port 8001
```

## Tests

```bash
source .venv/bin/activate && pytest -v
```

Phase 2 fixture slot: **78** (Wed 14:00). Phase 3: greedy → local search (seed 42, 200 iters) → negotiate gate.

## Phase 4 — seed + simulation

```bash
source .venv/bin/activate
python seed_synthetic.py                  # → data/synthetic_students.json (seed 20260903)
python run_simulation.py                  # full 300-student sim → SIMULATION_REPORT.md + data/simulation_stats.json
python run_simulation.py --subset 24      # fast smoke subset
```

Bitmaps stay member-side; formation soft scoring never sees them.

## Phase status

- **1:** dual SQLite, slot grid, `/healthz`, structural tests
- **2:** propose/respond/confirm, member evaluate, 40-round search, leakage tests
- **3:** greedy + local search + CONFIRM-only emit
- **4:** synthetic 300×12 population + formation/negotiation simulation report
