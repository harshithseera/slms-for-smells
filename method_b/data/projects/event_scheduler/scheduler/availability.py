"""Free-slot search across attendees."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from scheduler.calendar import Calendar


def _busy_periods(calendar: Calendar, attendees: list[str], start: datetime, end: datetime):
    wanted = set(attendees)
    periods = sorted(
        (max(e.start, start), min(e.end, end))
        for e in calendar.events_between(start, end)
        if wanted & set(e.attendees)
    )
    merged: list[list[datetime]] = []
    for s, e in periods:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def free_slots(calendar: Calendar, attendees: list[str], day: date, day_start: time = time(9, 0),
               day_end: time = time(17, 0), min_minutes: int = 30) -> list[tuple[datetime, datetime]]:
    start, end = datetime.combine(day, day_start), datetime.combine(day, day_end)
    slots, cursor = [], start
    for busy_start, busy_end in [*_busy_periods(calendar, attendees, start, end), [end, end]]:
        if busy_start - cursor >= timedelta(minutes=min_minutes):
            slots.append((cursor, busy_start))
        cursor = max(cursor, busy_end)
    return slots
