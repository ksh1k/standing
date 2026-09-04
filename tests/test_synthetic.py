"""Phase 4 synthetic seed + lightweight simulation smoke."""

from __future__ import annotations

from seed_synthetic import (
    COURSE_CODES,
    N_STUDENTS,
    SYNTHETIC_SEED,
    generate_population,
    population_checksum,
)
from run_simulation import run_sim


def test_seed_reproducible_checksum() -> None:
    a = generate_population(seed=SYNTHETIC_SEED)
    b = generate_population(seed=SYNTHETIC_SEED)
    assert a["checksum"] == b["checksum"]
    assert a["checksum"] == population_checksum(a["students"])
    assert [s["student_id"] for s in a["students"]] == [
        s["student_id"] for s in b["students"]
    ]


def test_population_structure_300x12() -> None:
    data = generate_population(seed=SYNTHETIC_SEED)
    assert data["n_students"] == N_STUDENTS == 300
    assert len(data["courses"]) == 12
    assert set(data["courses"]) == set(COURSE_CODES)
    assert len(data["students"]) == 300
    ids = [s["student_id"] for s in data["students"]]
    assert len(set(ids)) == 300
    for s in data["students"]:
        assert len(s["availability"]) == 224
        assert set(s["availability"]) <= {"0", "1"}
        assert s["courses"] and s["courses"][0] in COURSE_CODES
        assert "address" not in s and "dorm" not in s


def test_sim_smoke_subset() -> None:
    data = generate_population(seed=SYNTHETIC_SEED)
    stats = run_sim(data["students"][:24], seed=42, iters=30)
    assert stats["n_students"] == 24
    assert stats["students_placed"] + stats["students_unplaced"] == 24
    assert stats["n_groups_confirmed"] + stats["n_groups_failed"] >= 0


def test_full_sim_fast_report_stats() -> None:
    data = generate_population(seed=SYNTHETIC_SEED)
    stats = run_sim(data["students"], seed=42, iters=50)
    assert stats["n_students"] == 300
    assert stats["students_placed"] > 0
    assert stats["n_groups_confirmed"] > 0
    assert stats["n_groups_failed"] > 0  # conflict students create failures
    assert stats["mean_negotiation_rounds"] >= 1.0

