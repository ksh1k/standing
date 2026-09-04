"""Phase 3 group formation tests."""

from __future__ import annotations

from pathlib import Path

from standing.constants import (
    DEFAULT_GROUP_SIZE_MAX,
    DEFAULT_GROUP_SIZE_MIN,
    StudyStyle,
)
from standing.formation.greedy import best_pack_sizes, greedy_seed, naive_single_group
from standing.formation.local_search import local_search
from standing.formation.objective import (
    W_PLACE,
    partition_score,
)
from standing.formation.pipeline import (
    always_confirm_stub,
    form_groups,
    never_confirm_stub,
)
from tests.fixtures.formation_pool import (
    FAST_SLOT,
    make_student,
    pool_eight_same_course,
    pool_no_overlap,
    pool_soft_improvable,
)


def test_best_pack_sizes_maximizes_placement() -> None:
    assert best_pack_sizes(3) == []
    assert best_pack_sizes(8) == [4, 4]
    assert sum(best_pack_sizes(9)) == 9
    assert sum(best_pack_sizes(7)) == 6


def test_reproducibility_same_seed(tmp_path: Path) -> None:
    pool, members = pool_eight_same_course()
    r1 = form_groups(pool, members, seed=42, iters=50, log_dir=tmp_path / "a")
    r2 = form_groups(pool, members, seed=42, iters=50, log_dir=tmp_path / "b")
    assert [(g.group_id, g.member_ids, g.confirmed_slot) for g in r1.groups] == [
        (g.group_id, g.member_ids, g.confirmed_slot) for g in r2.groups
    ]
    assert r1.objective_before == r2.objective_before
    assert r1.objective_after == r2.objective_after


def test_hard_constraints_enforced(tmp_path: Path) -> None:
    pool, members = pool_eight_same_course()
    result = form_groups(pool, members, seed=42, iters=50, log_dir=tmp_path)
    assert result.groups, "expected at least one confirmed group"
    by_id = {s.student_id: s for s in pool}
    for g in result.groups:
        assert DEFAULT_GROUP_SIZE_MIN <= len(g.member_ids) <= DEFAULT_GROUP_SIZE_MAX
        courses = [set(by_id[sid].courses) for sid in g.member_ids]
        assert all(g.course_code in c for c in courses)
        assert g.confirmed_slot is not None


def test_objective_improves_or_equal_after_local_search() -> None:
    """Hill climbing: after >= before; mixed partition should rise."""
    _students, groups, unplaced, by_id = pool_soft_improvable()
    before = partition_score([m for _, _, m in groups], by_id)
    out, _u, score_before, score_after = local_search(
        groups, unplaced, by_id, seed=7, iters=500
    )
    assert score_before == before
    assert score_after >= score_before
    assert score_after > score_before, (score_before, score_after, out)


def test_placement_beats_naive_single_group(tmp_path: Path) -> None:
    """Greedy 4+4 beats naive single-group (≤6)."""
    pool, members = pool_eight_same_course()
    naive_groups, naive_left = naive_single_group(pool, "CSCE221")
    naive_placed = sum(len(m) for _, _, m in naive_groups)
    assert naive_placed == 6
    assert len(naive_left) == 2

    result = form_groups(
        pool,
        members,
        seed=42,
        iters=50,
        negotiator=always_confirm_stub,
        log_dir=tmp_path,
    )
    placed = sum(len(g.member_ids) for g in result.groups)
    assert placed > naive_placed
    assert placed == 8
    assert result.objective_after >= result.objective_before


def test_groups_without_unanimous_slot_not_emitted(tmp_path: Path) -> None:
    pool, members = pool_no_overlap()
    result = form_groups(pool, members, seed=42, iters=20, log_dir=tmp_path)
    assert result.groups == []
    assert result.rejected_candidates, "candidate should be attempted then dropped"
    assert set(result.unplaced) == {s.student_id for s in pool}


def test_never_confirm_stub_emits_nothing() -> None:
    pool, members = pool_eight_same_course()
    result = form_groups(
        pool, members, seed=42, iters=10, negotiator=never_confirm_stub
    )
    assert result.groups == []
    assert result.rejected_candidates


def test_integration_real_negotiation_confirms_fast_slot(tmp_path: Path) -> None:
    """Real NegotiateSession on fast bitmaps → CONFIRM."""
    pool, members = pool_eight_same_course()
    result = form_groups(pool, members, seed=42, iters=30, log_dir=tmp_path)
    assert result.groups
    for g in result.groups:
        assert g.confirmed_slot == FAST_SLOT

def test_greedy_seed_same_course_hard_constraint() -> None:
    pool = [
        make_student("x0", course="CSCE221", style=StudyStyle.DISCUSSION),
        make_student("x1", course="CSCE221", style=StudyStyle.DISCUSSION),
        make_student("x2", course="CSCE221", style=StudyStyle.DISCUSSION),
        make_student("x3", course="CSCE221", style=StudyStyle.DISCUSSION),
        make_student("y0", course="MATH304", style=StudyStyle.DISCUSSION),
        make_student("y1", course="MATH304", style=StudyStyle.DISCUSSION),
        make_student("y2", course="MATH304", style=StudyStyle.DISCUSSION),
        make_student("y3", course="MATH304", style=StudyStyle.DISCUSSION),
    ]
    groups, unplaced = greedy_seed(pool)
    assert not unplaced
    assert len(groups) == 2
    courses = {c for _, c, _ in groups}
    assert courses == {"CSCE221", "MATH304"}
    for _gid, course, members in groups:
        assert len(members) == 4
        for sid in members:
            stu = next(s for s in pool if s.student_id == sid)
            assert course in stu.courses


def test_objective_weights_prioritize_placement() -> None:
    """One placed student outweighs soft-only scores."""
    s = make_student("z0")
    one = partition_score([["z0"]], {"z0": s})
    assert one >= W_PLACE
