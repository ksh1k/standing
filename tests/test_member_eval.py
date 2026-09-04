"""Unit tests for pure member evaluate()."""

from __future__ import annotations

from standing.constants import SLOTS_PER_WEEK
from standing.negotiation.member_eval import evaluate, window_free
from standing.negotiation.messages import VerdictKind


def _busy() -> list[str]:
    return ["0"] * SLOTS_PER_WEEK


def _join(bits: list[str]) -> str:
    return "".join(bits)


def test_window_free_requires_three_slots() -> None:
    bits = _busy()
    bits[10] = bits[11] = "1"
    bits[12] = "0"
    assert not window_free(_join(bits), 10)
    bits[12] = "1"
    assert window_free(_join(bits), 10)


def test_evaluate_accept() -> None:
    bits = _busy()
    for i in range(10, 13):
        bits[i] = "1"
    v = evaluate(10, _join(bits))
    assert v.kind is VerdictKind.ACCEPT
    assert v.delta is None


def test_evaluate_reject_when_no_shift_works() -> None:
    bits = _busy()
    v = evaluate(10, _join(bits))
    assert v.kind is VerdictKind.REJECT


def test_evaluate_accept_if_shifted_plus_one() -> None:
    bits = _busy()
    # Proposed 10 busy; shifted +1 → 11 free.
    for i in range(11, 14):
        bits[i] = "1"
    v = evaluate(10, _join(bits))
    assert v.kind is VerdictKind.ACCEPT_IF_SHIFTED
    assert v.delta == 1


def test_evaluate_accept_if_shifted_minus_one_preferred_over_minus_two() -> None:
    bits = _busy()
    # Proposed 10 busy (slot 12 blocked). Free at 9 (-1) and 8 (-2); nearer -1 wins.
    for i in range(8, 12):
        bits[i] = "1"
    bits[12] = "0"
    v = evaluate(10, _join(bits))
    assert v.kind is VerdictKind.ACCEPT_IF_SHIFTED
    assert v.delta == -1
