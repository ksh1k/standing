"""Injectible clock for time-travel tests (never real sleep)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def parse_iso(value: str) -> datetime:
    """Parse ISO-8601; naive values treated as UTC."""
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class FrozenClock:
    """Mutable clock advanced explicitly in tests."""

    _now: datetime

    def __post_init__(self) -> None:
        if self._now.tzinfo is None:
            self._now = self._now.replace(tzinfo=timezone.utc)
        else:
            self._now = self._now.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def set(self, when: datetime) -> datetime:
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        else:
            when = when.astimezone(timezone.utc)
        self._now = when
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        self._now = self._now + delta
        return self._now
