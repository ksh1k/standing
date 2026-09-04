"""Greedy seed: pack by course to maximize placement, then soft-fill groups."""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

from standing.constants import DEFAULT_GROUP_SIZE_MAX, DEFAULT_GROUP_SIZE_MIN
from standing.formation.objective import FormationStudent, group_soft_score
from standing.models import normalize_course_code

MIN_G = DEFAULT_GROUP_SIZE_MIN
MAX_G = DEFAULT_GROUP_SIZE_MAX


def best_pack_sizes(n: int) -> list[int]:
    """Group sizes in [4,6] maximizing students placed, then number of groups.

    Deterministic tie-break: among equal (placed, n_groups), prefer the size
    multiset whose descending-sorted tuple is lexicographically largest.
    """
    if n < MIN_G:
        return []
    best_key: tuple[int, int, tuple[int, ...]] = (-1, -1, ())
    best: list[int] = []
    for n6 in range(n // 6, -1, -1):
        rem6 = n - 6 * n6
        for n5 in range(rem6 // 5, -1, -1):
            rem5 = rem6 - 5 * n5
            n4 = rem5 // 4
            sizes = [6] * n6 + [5] * n5 + [4] * n4
            if not sizes:
                continue
            key = (sum(sizes), len(sizes), tuple(sorted(sizes, reverse=True)))
            if key > best_key:
                best_key = key
                best = sizes
    return best


def _fill_score(
    candidate: FormationStudent, current: Sequence[FormationStudent]
) -> float:
    return group_soft_score([*current, candidate])


def _assign_to_sizes(
    eligible: list[FormationStudent], sizes: list[int]
) -> tuple[list[list[str]], list[str]]:
    """Fill groups of given sizes from eligible (mutates a local remaining list)."""
    remaining = list(eligible)
    remaining.sort(key=lambda s: (s.study_style.value, s.student_id))
    groups: list[list[str]] = []
    for target in sizes:
        if len(remaining) < target:
            break
        members: list[FormationStudent] = [remaining.pop(0)]
        while len(members) < target and remaining:
            best_i = 0
            best_sc = _fill_score(remaining[0], members)
            for i in range(1, len(remaining)):
                sc = _fill_score(remaining[i], members)
                if sc > best_sc or (
                    sc == best_sc
                    and remaining[i].student_id < remaining[best_i].student_id
                ):
                    best_sc = sc
                    best_i = i
            members.append(remaining.pop(best_i))
        groups.append([m.student_id for m in members])
    unplaced = [s.student_id for s in remaining]
    return groups, unplaced


def seed_groups_for_course(
    course: str,
    pool: Sequence[FormationStudent],
) -> tuple[list[list[str]], list[str]]:
    """Greedy-assign students who take ``course`` into packed groups."""
    eligible = [s for s in pool if course in s.courses]
    sizes = best_pack_sizes(len(eligible))
    if not sizes:
        return [], [s.student_id for s in eligible]
    return _assign_to_sizes(eligible, sizes)


def greedy_seed(
    pool: Sequence[FormationStudent],
    *,
    group_id_prefix: str = "g",
) -> tuple[list[tuple[str, str, list[str]]], list[str]]:
    """Seed candidate groups across the pool.

    Returns ``(groups, unplaced_ids)`` where each group is
    ``(group_id, course_code, member_ids)``. Each student joins at most one
    group. Courses are tried in descending eligible-count order (tie-break
    course code) so multi-course students prefer larger markets first.
    """
    by_id: dict[str, FormationStudent] = {s.student_id: s for s in pool}
    for s in pool:
        s.courses = [normalize_course_code(c) for c in s.courses]

    course_to_ids: dict[str, list[str]] = defaultdict(list)
    for s in pool:
        for code in dict.fromkeys(s.courses):  # stable unique
            course_to_ids[code].append(s.student_id)

    course_order = sorted(
        course_to_ids.keys(),
        key=lambda c: (-len(course_to_ids[c]), c),
    )

    placed: set[str] = set()
    out: list[tuple[str, str, list[str]]] = []
    g_idx = 0
    for course in course_order:
        available = [
            by_id[sid]
            for sid in sorted(course_to_ids[course])
            if sid not in placed and course in by_id[sid].courses
        ]
        groups, _left = seed_groups_for_course(course, available)
        for members in groups:
            out.append((f"{group_id_prefix}{g_idx}", course, members))
            g_idx += 1
            placed.update(members)

    unplaced = sorted(s.student_id for s in pool if s.student_id not in placed)
    return out, unplaced


def naive_single_group(
    pool: Sequence[FormationStudent],
    course: str,
    *,
    group_id: str = "naive0",
) -> tuple[list[tuple[str, str, list[str]]], list[str]]:
    """Baseline: one largest valid group for ``course``, rest unplaced."""
    eligible = sorted(
        [s for s in pool if course in s.courses],
        key=lambda s: (s.study_style.value, s.student_id),
    )
    if len(eligible) < MIN_G:
        return [], [s.student_id for s in eligible]
    take = min(MAX_G, len(eligible))
    members = [s.student_id for s in eligible[:take]]
    unplaced = [s.student_id for s in eligible[take:]]
    return [(group_id, course, members)], unplaced
