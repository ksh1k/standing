"""Local search over group partitions using swap / reassign moves."""

from __future__ import annotations

import random
from typing import Mapping, Sequence

from standing.constants import DEFAULT_GROUP_SIZE_MAX, DEFAULT_GROUP_SIZE_MIN
from standing.formation.objective import FormationStudent, partition_score

MIN_G = DEFAULT_GROUP_SIZE_MIN
MAX_G = DEFAULT_GROUP_SIZE_MAX

# Defaults documented in DECISIONS.md
DEFAULT_SEED: int = 42
DEFAULT_ITERS: int = 200


def local_search(
    groups: Sequence[tuple[str, str, list[str]]],
    unplaced: Sequence[str],
    students: Mapping[str, FormationStudent],
    *,
    seed: int = DEFAULT_SEED,
    iters: int = DEFAULT_ITERS,
) -> tuple[list[tuple[str, str, list[str]]], list[str], float, float]:
    """Hill-climb with random swap moves; return improved partition + scores.

    Moves (same course only):
      0. Swap one member between two groups
      1. Swap a placed member with an unplaced student who shares the course
      2. Move an unplaced student into a group with room (< max size)
      3. Form a new group from ≥4 unplaced students sharing a course

    Accepts a move only if ``partition_score`` strictly increases.
    Reports objective BEFORE and AFTER local search.
    """
    cur_groups: list[tuple[str, str, list[str]]] = [
        (gid, course, list(members)) for gid, course, members in groups
    ]
    cur_unplaced: list[str] = list(unplaced)
    score_before = partition_score([m for _, _, m in cur_groups], students)
    best_score = score_before
    rng = random.Random(seed)

    next_idx = 0
    for gid, _, _ in cur_groups:
        if gid.startswith("g") and gid[1:].isdigit():
            next_idx = max(next_idx, int(gid[1:]) + 1)

    def _score() -> float:
        return partition_score([m for _, _, m in cur_groups], students)

    def _course_indices() -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for i, (_, course, _) in enumerate(cur_groups):
            out.setdefault(course, []).append(i)
        return out

    for _ in range(iters):
        course_map = _course_indices()
        move = rng.randint(0, 3)

        if move == 0 and course_map:
            course = rng.choice(list(course_map.keys()))
            idxs = course_map[course]
            if len(idxs) < 2:
                continue
            i, j = rng.sample(idxs, 2)
            gi = cur_groups[i][2]
            gj = cur_groups[j][2]
            if not gi or not gj:
                continue
            a = rng.randrange(len(gi))
            b = rng.randrange(len(gj))
            gi[a], gj[b] = gj[b], gi[a]
            sc = _score()
            if sc > best_score:
                best_score = sc
            else:
                gi[a], gj[b] = gj[b], gi[a]

        elif move == 1 and cur_groups and cur_unplaced:
            gi_idx = rng.randrange(len(cur_groups))
            _gid, course, members = cur_groups[gi_idx]
            candidates = [
                u for u in cur_unplaced if course in students[u].courses
            ]
            if not members or not candidates:
                continue
            a = rng.randrange(len(members))
            u = rng.choice(candidates)
            old = members[a]
            members[a] = u
            cur_unplaced.remove(u)
            cur_unplaced.append(old)
            sc = _score()
            if sc > best_score:
                best_score = sc
            else:
                members[a] = old
                cur_unplaced.remove(old)
                cur_unplaced.append(u)

        elif move == 2 and cur_groups and cur_unplaced:
            gi_idx = rng.randrange(len(cur_groups))
            _gid, course, members = cur_groups[gi_idx]
            if len(members) >= MAX_G:
                continue
            candidates = [
                u for u in cur_unplaced if course in students[u].courses
            ]
            if not candidates:
                continue
            u = rng.choice(candidates)
            members.append(u)
            cur_unplaced.remove(u)
            sc = _score()
            if sc > best_score:
                best_score = sc
            else:
                members.pop()
                cur_unplaced.append(u)

        else:
            # New group from unplaced sharing a course
            by_c: dict[str, list[str]] = {}
            for u in cur_unplaced:
                for c in students[u].courses:
                    by_c.setdefault(c, []).append(u)
            formable = sorted(
                c for c, ids in by_c.items() if len(set(ids)) >= MIN_G
            )
            if not formable:
                continue
            course = rng.choice(formable)
            ids = sorted(set(by_c[course]))
            take = min(MAX_G, len(ids))
            chosen = ids[:take]
            for sid in chosen:
                cur_unplaced.remove(sid)
            new_gid = f"g{next_idx}"
            next_idx += 1
            cur_groups.append((new_gid, course, list(chosen)))
            sc = _score()
            if sc > best_score:
                best_score = sc
            else:
                cur_groups.pop()
                cur_unplaced.extend(chosen)

    canon = [
        (gid, course, sorted(members)) for gid, course, members in cur_groups
    ]
    canon.sort(key=lambda t: (t[1], t[0]))
    cur_unplaced = sorted(set(cur_unplaced))
    score_after = partition_score([m for _, _, m in canon], students)
    return canon, cur_unplaced, score_before, score_after
