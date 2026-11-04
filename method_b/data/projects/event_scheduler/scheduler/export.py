"""CSV and simplified iCalendar export."""
from __future__ import annotations

from collections.abc import Iterable

from scheduler.events import Event


def _by_start(events: Iterable[Event]) -> list[Event]:
    return sorted(events, key=lambda e: e.start)


def to_csv(events: Iterable[Event]) -> str:
    rows = ["id,title,start,end,attendees"]
    for e in _by_start(events):
        rows.append(",".join([e.event_id, e.title, f"{e.start:%Y-%m-%d %H:%M}", f"{e.end:%Y-%m-%d %H:%M}",
                              ";".join(e.attendees)]))
    return "\n".join(rows)


def to_ics(events: Iterable[Event]) -> str:
    lines = ["BEGIN:VCALENDAR"]
    for e in _by_start(events):
        lines += ["BEGIN:VEVENT", f"UID:{e.event_id}", f"SUMMARY:{e.title}",
                  f"DTSTART:{e.start:%Y%m%dT%H%M%S}", f"DTEND:{e.end:%Y%m%dT%H%M%S}"]
        lines += [f"ATTENDEE:{a}" for a in e.attendees]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\n".join(lines)
