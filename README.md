# Standing

Campus study groups that pick a shared weekly meetup **without anyone sharing their full calendar**. Students see only place and time. Availability stays on the member side.

## Product

1. **Join** — display name + a self-chosen student code (no university login).
2. **Preferences** — courses, study style, public campus zone, time-of-day weights.
3. **Match** — when a course pool has at least 4 students, Standing forms a group and negotiates a slot everyone can take.
4. **My groups** — confirmed session only: campus wall-clock time and a public place.

Open [http://127.0.0.1:8000/join.html](http://127.0.0.1:8000/join.html) after you start the server.

## Hard constraints

1. No real university systems, portals, or university credentials.
2. No residence data. Location prefs are coarse public campus zones only.
3. Availability bitmaps never leave the member store. The coordinator sees accept/reject only.
4. Attendance is private to that student.
5. Groups are 4–6 people, public places only. No 1:1 first meetings.
6. Do not post externally or ship a public URL without an explicit ask.

## Stack

Python 3.11+, SQLite (stdlib), FastAPI, uvicorn, pytest, icalendar. UI is plain HTML/CSS/JS in `static/` — no build step.

## Layout

```
standing/          package: coordinator, member, formation, negotiation, persistence
static/            Join, My groups, Demo pages
tests/             constraint, negotiation, formation, UI
seed_synthetic.py  reproducible synthetic population
run_simulation.py  form + negotiate report
data/              local SQLite and logs (gitignored)
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python -m standing.demo_server
```

Then open **http://127.0.0.1:8000/**.

- Join: `/join.html`
- My groups: `/groups.html`
- Demo dashboard (live transcript + sample negotiate): `/dashboard.html`

The member API is mounted on the same process at `/member`, so one server is enough for the product flow.

## Tests

```bash
pytest -v
```

## Notes

Session times are stored as campus wall-clock. My groups renders that label from the API (`when_label`) so a browser timezone cannot shift 2:00 PM to morning.

More context: [DECISIONS.md](DECISIONS.md) · click-through: [DEMO.md](DEMO.md)
