# Simulation report (Phase 4)

- Population: **300** students
- Students placed: **208**
- Students unplaced: **92**
- Groups confirmed: **51**
- Groups failed (no slot): **21**
- Mean negotiation rounds (confirmed): **1.0**
- Formation objective: 300065118.63 → 300065122.15

## Group size distribution

- size 4: 47 groups
- size 5: 4 groups

## Notes

- Pipeline: greedy → local search (seed 42) → real NegotiateSession (budget 40).
- Availability bitmaps stay on member side; soft scoring never sees them.
- Compatible students share weekday evening free windows → fast CONFIRM;
  ~12% conflict students (morning-only) cause some groups to fail.
