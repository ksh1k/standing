#!/usr/bin/env python3
"""Run Phase 3 formation + negotiation on the synthetic population.

Usage:
  python run_simulation.py                 # full 300-student sim → report
  python run_simulation.py --subset 24     # fast smoke subset
  python seed_synthetic.py && python run_simulation.py
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from seed_synthetic import DEFAULT_OUT, load_population, write_population
from standing.constants import CampusZone, StudyStyle, YearLevel
from standing.formation.objective import FormationStudent
from standing.formation.pipeline import form_groups
from standing.models import TimeOfDayWeights
from standing.negotiation.coordinator_negotiate import InProcessMember, NegotiateSession

ROOT = Path(__file__).resolve().parent
REPORT_MD = ROOT / "SIMULATION_REPORT.md"
STATS_JSON = ROOT / "data" / "simulation_stats.json"


class _NullLog:
    def append(self, record: Any) -> None:  # noqa: ANN401
        return


def _tod(d: dict[str, float]) -> TimeOfDayWeights:
    return TimeOfDayWeights(
        morning=float(d["morning"]),
        afternoon=float(d["afternoon"]),
        evening=float(d["evening"]),
    )


def records_to_pool(
    records: list[dict[str, Any]],
) -> tuple[list[FormationStudent], dict[str, InProcessMember], dict[str, TimeOfDayWeights]]:
    pool: list[FormationStudent] = []
    members: dict[str, InProcessMember] = {}
    tod_map: dict[str, TimeOfDayWeights] = {}
    for r in records:
        sid = r["student_id"]
        tod = _tod(r["time_of_day_preference"])
        pool.append(
            FormationStudent(
                student_id=sid,
                year=YearLevel(r["year"]),
                courses=list(r["courses"]),
                preferred_group_size=int(r["preferred_group_size"]),
                preferred_zones=[CampusZone(z) for z in r["preferred_zones"]],
                study_style=StudyStyle(r["study_style"]),
            )
        )
        members[sid] = InProcessMember(sid, r["availability"], tod)
        tod_map[sid] = tod
    return pool, members, tod_map


def run_sim(
    records: list[dict[str, Any]],
    *,
    seed: int = 42,
    iters: int = 200,
) -> dict[str, Any]:
    pool, members, tod_map = records_to_pool(records)
    rounds_confirmed: list[int] = []
    def negotiator(gid, mems, tods):  # noqa: ANN001
        session = NegotiateSession(
            group_id=gid, members=mems, member_tod=tods,
            log=_NullLog(), budget=40,  # type: ignore[arg-type]
        )
        result = session.run()
        if result.status == "confirmed" and result.start_slot is not None:
            rounds_confirmed.append(result.rounds)
            return True, result.start_slot
        return False, None

    result = form_groups(
        pool, members, tod_map, seed=seed, iters=iters, negotiator=negotiator
    )

    size_dist = Counter(len(g.member_ids) for g in result.groups)
    placed = sum(len(g.member_ids) for g in result.groups)
    mean_rounds = (
        float(statistics.mean(rounds_confirmed)) if rounds_confirmed else 0.0
    )
    return {
        "n_students": len(records),
        "n_groups_confirmed": len(result.groups),
        "n_groups_failed": len(result.rejected_candidates),
        "students_placed": placed,
        "students_unplaced": len(result.unplaced),
        "group_size_distribution": {str(k): size_dist[k] for k in sorted(size_dist)},
        "mean_negotiation_rounds": round(mean_rounds, 3),
        "confirmed_rounds": rounds_confirmed,
        "objective_before": round(result.objective_before, 2),
        "objective_after": round(result.objective_after, 2),
    }


def write_report(stats: dict[str, Any], path: Path = REPORT_MD) -> None:
    dist = stats["group_size_distribution"]
    dist_lines = "\n".join(f"- size {k}: {v} groups" for k, v in dist.items()) or "- (none)"
    path.write_text(
        "\n".join(
            [
                "# Simulation report (Phase 4)",
                "",
                f"- Population: **{stats['n_students']}** students",
                f"- Students placed: **{stats['students_placed']}**",
                f"- Students unplaced: **{stats['students_unplaced']}**",
                f"- Groups confirmed: **{stats['n_groups_confirmed']}**",
                f"- Groups failed (no slot): **{stats['n_groups_failed']}**",
                f"- Mean negotiation rounds (confirmed): **{stats['mean_negotiation_rounds']}**",
                f"- Formation objective: {stats['objective_before']} → {stats['objective_after']}",
                "",
                "## Group size distribution",
                "",
                dist_lines,
                "",
                "## Notes",
                "",
                "- Pipeline: greedy → local search (seed 42) → real NegotiateSession (budget 40).",
                "- Availability bitmaps stay on member side; soft scoring never sees them.",
                "- Compatible students share weekday evening free windows → fast CONFIRM;",
                "  ~12% conflict students (morning-only) cause some groups to fail.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--subset", type=int, default=0, help="Use first N students (0=all)")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    if args.data.exists():
        data = load_population(args.data)
    else:
        write_population(args.data)
        data = load_population(args.data)

    records = list(data["students"])
    if args.subset and args.subset > 0:
        records = records[: args.subset]

    stats = run_sim(records, iters=args.iters)
    STATS_JSON.parent.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in stats.items() if k != "confirmed_rounds"}
    STATS_JSON.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    if not args.no_report and not args.subset:
        write_report(stats)
        print(f"wrote {REPORT_MD}")
    print(
        f"placed={stats['students_placed']}/{stats['n_students']} "
        f"groups_ok={stats['n_groups_confirmed']} failed={stats['n_groups_failed']} "
        f"mean_rounds={stats['mean_negotiation_rounds']} "
        f"size_dist={stats['group_size_distribution']}"
    )


if __name__ == "__main__":
    main()
