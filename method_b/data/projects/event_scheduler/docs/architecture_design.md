# Architecture Design

File tree:
```bash
├── scheduler
│   ├── __init__.py
│   ├── errors.py
│   ├── events.py
│   ├── recurrence.py
│   ├── calendar.py
│   ├── availability.py
│   └── export.py
```

Layering (a module only imports modules listed before it):
`errors` → `events` → `recurrence` → `calendar` → `availability`; `export` depends only on
`events`.

`errors.py`: `SchedulerError`, `ConflictError`, `UnknownEvent`.

`events.py`: `Event` (dataclass) with `duration_minutes`, `overlaps`, `shares_attendee`.

`recurrence.py`: `class RecurrenceRule(frequency, interval=1, count=None, until=None)` with
`occurrences(start)`.

`calendar.py`: `class Calendar()` with `add`, `add_recurring`, `get`, `remove`, `events_on`,
`events_between`, `agenda_for`.

`availability.py`: module-level `free_slots(calendar, attendees, day, day_start=time(9, 0),
day_end=time(17, 0), min_minutes=30)`.

`export.py`: module-level `to_csv(events)` and `to_ics(events)`.

Usage example:
```python
from datetime import date, datetime
from scheduler.availability import free_slots
from scheduler.calendar import Calendar
from scheduler.events import Event
from scheduler.recurrence import RecurrenceRule

cal = Calendar()
standup = Event("standup", "Stand-up", datetime(2026, 3, 2, 9, 30), datetime(2026, 3, 2, 9, 45), ["ana", "ben"])
cal.add_recurring(standup, RecurrenceRule("weekdays", count=5))
print(free_slots(cal, ["ana"], date(2026, 3, 2)))
```
