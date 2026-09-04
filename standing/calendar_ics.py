"""Generate .ics for scheduled groups (title / location / time only)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from icalendar import Calendar, Event

from standing.constants import (
    DAY_NAMES,
    GRID_START_HOUR,
    MEETING_DURATION_SLOTS,
    SLOT_MINUTES,
    SLOTS_PER_DAY,
    is_legal_meeting_start,
)

DEFAULT_WEEK_MONDAY: date = date(2026, 9, 7)  # Monday


def slot_start_datetime(start_slot: int, week_monday: date | None = None) -> datetime:
    if not is_legal_meeting_start(start_slot):
        raise ValueError(f"illegal meeting start: {start_slot}")
    monday = week_monday or DEFAULT_WEEK_MONDAY
    day, sid = divmod(start_slot, SLOTS_PER_DAY)
    minutes = GRID_START_HOUR * 60 + sid * SLOT_MINUTES
    return datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc) + timedelta(
        days=day, minutes=minutes
    )


def slot_label(start_slot: int) -> str:
    day, sid = divmod(start_slot, SLOTS_PER_DAY)
    minutes = GRID_START_HOUR * 60 + sid * SLOT_MINUTES
    hh, mm = divmod(minutes, 60)
    return f"{DAY_NAMES[day]} {hh:02d}:{mm:02d}"


def build_group_ics(
    *, title: str, location: str, start: datetime, uid: str | None = None
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Standing//study-group//EN")
    cal.add("version", "2.0")
    ev = Event()
    ev.add("summary", title)
    ev.add("location", location)
    ev.add("dtstart", start)
    ev.add("dtend", start + timedelta(minutes=MEETING_DURATION_SLOTS * SLOT_MINUTES))
    if uid:
        ev.add("uid", uid)
    cal.add_component(ev)
    return cal.to_ical()


def ics_from_slot(
    *, title: str, location: str, start_slot: int, week_monday: date | None = None, uid: str | None = None
) -> bytes:
    return build_group_ics(
        title=title, location=location, start=slot_start_datetime(start_slot, week_monday), uid=uid
    )

