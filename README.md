# Standing

Local study-group coordination for campus peers. Enrollment is self-reported or synthetic; everything binds to localhost.

## Hard constraints

1. No real university systems (no tamu.edu / portals / LMS; no university credentials).
2. No residence data — location prefs are coarse public campus zones only.
3. Availability bitmaps stay in the owning member agent; coordinator sees only accept/reject for proposed slots.
4. Individual attendance is private to that student.
5. Group meetings (size 4–6) in public places only — never 1:1 first meetings or residential locations.
6. Localhost only — no public deploy, email, or external posts without asking.

## Architecture (brief)

- **Member agents** hold availability bitmaps, display names, ToD prefs, and private attendance. They answer PROPOSE with RESPOND (accept / reject / accept_if_shifted) — no bitmap leaves the member.
- **Coordinator** forms groups (greedy + local search), runs negotiation (PROPOSE / RESPOND / CONFIRM), stores aggregates + scheduled slot/zone only. Dual SQLite DBs keep private fields off the coordinator.
- **UI** (`static/`): intake, my groups, coordinator dashboard with live transcript + demo negotiate + `.ics` download.
- **Synthetic path:** `seed_synthetic.py` (300×12) → `run_simulation.py` → `SIMULATION_REPORT.md`.

Details: [DECISIONS.md](DECISIONS.md) · Demo script: [DEMO.md](DEMO.md) · Sim results: [SIMULATION_REPORT.md](SIMULATION_REPORT.md)

## Stack

Python 3.11+, SQLite (stdlib), FastAPI + uvicorn, pytest, icalendar. No React/Docker/ORM/cloud.

## Layout

```
standing/            # package: constants, models, db, negotiation, formation, persistence, calendar_ics
static/              # plain HTML/JS/CSS (no build)
seed_synthetic.py    # reproducible 300 students × 12 courses
run_simulation.py    # form + negotiate → SIMULATION_REPORT.md
data/                # synthetic JSON, negotiation_log.jsonl, local SQLite (gitignored artifacts)
tests/               # constraint / negotiation / formation / synthetic / persistence / UI tests
DEMO.md              # 3-minute click-by-click demo
DECISIONS.md
SIMULATION_REPORT.md
```

## Fresh clone — setup

```bash
cd standing
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## One command each (venv active, repo root)

**Start the system** (coordinator UI + transcript + demo negotiate on localhost:8000):

```bash
python -m standing.demo_server
```

Then open **http://127.0.0.1:8000/** → Dashboard → **Run 5-student demo negotiate**.  
Optional member agent (intake / my groups):

```bash
uvicorn standing.member.app:app --host 127.0.0.1 --port 8001
```

**Seed 300 synthetic students:**

```bash
python seed_synthetic.py
```

Writes `data/synthetic_students.json` (reproducible seed `20260903`).

**Run the test suite:**

```bash
pytest -v
```

**Optional simulation** (after seed):

```bash
python run_simulation.py            # full population
python run_simulation.py --subset 24
```

## Demo (~3 minutes)

See **[DEMO.md](DEMO.md)** for exact click-by-click steps and timing cues.

## Phase status

- **1:** dual SQLite, slot grid, `/healthz`, structural tests
- **2:** propose/respond/confirm, member evaluate, 40-round search, leakage tests
- **3:** greedy + local search + CONFIRM-only emit
- **4:** synthetic 300×12 population + formation/negotiation simulation report
- **5:** persistence — reminders, dormancy, drift renegotiation, exam-season second session, merge flags
- **6:** plain HTML UI (intake / my groups / live transcript), `.ics`, demo negotiate endpoint
- **7:** DEMO.md, README runbook, clean-clone verification (FINAL)
