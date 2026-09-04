#!/usr/bin/env python3
"""Generate a reproducible synthetic Standing population (300 students, 12 courses).

Usage:
  python seed_synthetic.py              # write data/synthetic_students.json
  python seed_synthetic.py --out PATH
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from standing.constants import (
    SLOTS_PER_DAY,
    SLOTS_PER_WEEK,
    CampusZone,
    StudyStyle,
    YearLevel,
)

SYNTHETIC_SEED: int = 20260903
N_STUDENTS: int = 300

# 12 courses with (code, class_day 0-6, class_slot_in_day) — class blocks stay busy.
COURSES: tuple[tuple[str, int, int], ...] = (
    ("CSCE121", 0, 6),
    ("CSCE221", 0, 10),
    ("CSCE314", 1, 6),
    ("CSCE315", 1, 12),
    ("MATH151", 2, 4),
    ("MATH152", 2, 10),
    ("MATH304", 3, 6),
    ("PHYS206", 3, 14),
    ("PHYS207", 4, 6),
    ("ENGL104", 4, 10),
    ("STAT211", 0, 16),
    ("ECEN214", 2, 16),
)
COURSE_CODES: tuple[str, ...] = tuple(c[0] for c in COURSES)

_YEARS = tuple(YearLevel)
_STYLES = tuple(StudyStyle)
_ZONES = tuple(CampusZone)

DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "synthetic_students.json"


def _mark_range(bits: list[str], day: int, start: int, end: int) -> None:
    base = day * SLOTS_PER_DAY
    for s in range(start, end):
        bits[base + s] = "1"


def build_availability(rng: random.Random, *, conflict: bool) -> str:
    """Clustered free windows: compatible → weekday evenings; conflict → mornings.

    Class times are never freed (start from all-busy). Weekend afternoon jitter
    on compatible students adds variance without blocking evening convergence.
    """
    bits = ["0"] * SLOTS_PER_WEEK
    if conflict:
        for day in range(5):
            _mark_range(bits, day, 0, 9)
    else:
        for day in range(5):
            _mark_range(bits, day, 20, 30)
        if rng.random() < 0.55:
            _mark_range(bits, 5, 10, 20)  # Sat afternoon
        if rng.random() < 0.35:
            _mark_range(bits, 6, 10, 18)  # Sun afternoon
    return "".join(bits)


def population_checksum(students: list[dict[str, Any]]) -> str:
    blob = json.dumps(students, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def generate_population(
    seed: int = SYNTHETIC_SEED, n_students: int = N_STUDENTS
) -> dict[str, Any]:
    """Deterministic population: ~equal per course, ~12% conflict availability."""
    rng = random.Random(seed)
    # Round-robin course assignment so each course gets n_students // 12 (+ rem).
    codes = list(COURSE_CODES)
    assignments = [codes[i % len(codes)] for i in range(n_students)]
    rng.shuffle(assignments)

    students: list[dict[str, Any]] = []
    for i in range(n_students):
        sid = f"stu{i:03d}"
        course = assignments[i]
        conflict = rng.random() < 0.12
        tod = (
            {"morning": 5.0, "afternoon": 1.0, "evening": 0.5}
            if conflict
            else {"morning": 0.5, "afternoon": 1.0, "evening": 5.0}
        )
        zones = [rng.choice(_ZONES).value]
        if rng.random() < 0.4:
            z2 = rng.choice(_ZONES).value
            if z2 not in zones:
                zones.append(z2)
        students.append(
            {
                "student_id": sid,
                "year": rng.choice(_YEARS).value,
                "courses": [course],
                "preferred_group_size": rng.choice((4, 4, 5, 5, 6)),
                "preferred_zones": zones,
                "study_style": rng.choice(_STYLES).value,
                "time_of_day_preference": tod,
                "availability": build_availability(rng, conflict=conflict),
                "conflict": conflict,
            }
        )
    students.sort(key=lambda s: s["student_id"])
    return {
        "seed": seed,
        "n_students": n_students,
        "courses": list(COURSE_CODES),
        "checksum": population_checksum(students),
        "students": students,
    }


def write_population(path: Path | None = None, seed: int = SYNTHETIC_SEED) -> Path:
    out = path or DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    data = generate_population(seed=seed)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def load_population(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_OUT
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=SYNTHETIC_SEED)
    args = ap.parse_args()
    path = write_population(args.out, seed=args.seed)
    data = load_population(path)
    print(f"wrote {path} students={data['n_students']} courses={len(data['courses'])}")
    print(f"seed={data['seed']} checksum={data['checksum'][:16]}...")


if __name__ == "__main__":
    main()
