# Standing — 3-minute demo script

**Goal:** Show five member agents negotiate a meeting slot while proving schedule bitmaps never leave the members. Fit in ~3 minutes.

**Prerequisites:** Repo root, venv active (`source .venv/bin/activate`), deps installed (`pip install -r requirements.txt`).

---

## 0:00–0:20 — Start the system

**Terminal A (required — coordinator + static UI):**

```bash
cd /path/to/standing && source .venv/bin/activate
python -m standing.demo_server
```

Wait for uvicorn: `Uvicorn running on http://127.0.0.1:8000`.

**Terminal B (optional — intake / my groups):**

```bash
cd /path/to/standing && source .venv/bin/activate
uvicorn standing.member.app:app --host 127.0.0.1 --port 8001
```

**Talking point:** Both bind `127.0.0.1` only (constraint 6). No university systems, no email.

---

## 0:20–0:35 — Open coordinator dashboard

1. Browser → **http://127.0.0.1:8000/**
2. Click **Dashboard** (or go directly to **http://127.0.0.1:8000/dashboard.html**).
3. Point at **Live negotiation transcript** — page already polls `/api/transcript` every 1s.

**Talking point:** UI is plain HTML/JS; no React build. Coordinator never stores availability bitmaps.

---

## 0:35–1:45 — Run 5-student demo negotiate (core)

1. Click **Run 5-student demo negotiate**.
2. Status should flip to **Negotiation running…** then settle on something like  
   `Last: confirmed slot=78 rounds=…`.
3. Watch the transcript fill with message types:

| Type | What you see | What you do *not* see |
|------|----------------|------------------------|
| **PROPOSE** | `slot=N` | bitmaps, free/busy grids |
| **RESPOND** | `slot=N` + verdict (`accept` / `reject` / `accept_if_shifted`) | **no `student_id`**, no availability string |
| **CONFIRM** | `slot=N` (fixture expects **78** = Wed 14:00) | individual schedules |

4. Scroll the transcript; emphasize aloud:  
   **“Only accept/reject (and optional shift hints) crossed the wire. Availability bitmaps stayed inside each member agent.”**

**Talking point:** Fixture five students share a unanimous free window at slot 78; coordinator scores with ToD weights only.

---

## 1:45–2:15 — Scheduled groups + .ics

1. On the same dashboard, under **Scheduled groups**, click **Refresh groups** (or wait — page loads groups on open).
2. Confirm a new **CSCE315** group appears: slot label ~Wednesday 14:00, zone `main_library`, member count 5.
3. Click **Download .ics** on that card → calendar file with SUMMARY / LOCATION (public zone) / DTSTART–DTEND (90 min). No ATTENDEE list of private emails.

**Talking point:** Public campus zone only — never residence (constraints 2 / 5).

---

## 2:15–2:50 — Optional: intake + my groups

*Skip if short on time; requires Terminal B (member :8001).*

1. Nav → **Intake**.
2. Fill: Student ID `s0`, Display name `Alex`, course `CSCE315`, leave zone `main_library` checked → **Save profile**.
3. Nav → **My groups** → student_id `s0` → **Load my sessions**.
4. Show time + public place only (sessions written when demo negotiate confirmed).

**Talking point:** Member DB holds display name + availability; coordinator groups API returns time/zone/counts — not attendance (constraint 4).

---

## 2:50–3:00 — Close

1. Re-open dashboard transcript if needed; repeat one-liner: **no schedule data crossed**.
2. Optional one-liner: seed + sim for scale — `python seed_synthetic.py && python run_simulation.py --subset 24` (not required live).

**Hard constraints reminder (say one):** Groups are 4–6 in public places; localhost only; no LMS/credentials.

---

## Timing cheat-sheet

| Clock | Action |
|-------|--------|
| 0:00 | Start `python -m standing.demo_server` |
| 0:20 | Open `/dashboard.html` |
| 0:35 | Click **Run 5-student demo negotiate** |
| 0:40–1:45 | Narrate PROPOSE / RESPOND / CONFIRM — no bitmaps |
| 1:45 | Refresh groups + download `.ics` |
| 2:15 | Optional intake / my groups |
| 2:50 | Wrap: privacy + localhost |

## If something fails

- Port in use → kill prior uvicorn or change nothing (demo assumes 8000/8001).
- Empty transcript → click **Start polling**, then run demo again.
- Intake errors → ensure member app is up on `127.0.0.1:8001`.
- Health check: `curl -s http://127.0.0.1:8000/healthz` → `{"status":"ok","service":"coordinator"}`.
