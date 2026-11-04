# Product Requirements Document: Team Event Scheduler

## 1. Overview
A Python package (`scheduler`) that keeps a team calendar: one-off and recurring events
with attendees, conflict detection per attendee, free-slot search within working hours,
and export to CSV and a simplified iCalendar format. In memory only; no UI, network,
time zones or system clock (callers always pass explicit `datetime`/`date` values).

## 2. Goals
- Nobody is double-booked: an attendee can never be in two overlapping events.
- Recurring meetings are created in one step and either fully or not at all.
- People can find free time with each other quickly.
- Calendars can be exported for other tools.

## 3. Constraints
- Python 3.12, standard library only. Naive `datetime` objects (no time zones).

## 4. Functional requirements

### 4.1 Errors (`scheduler/errors.py`)
`SchedulerError` is the base class of `ConflictError` and `UnknownEvent`.

### 4.2 Events (`scheduler/events.py`)
**Event** (dataclass): `event_id` (str), `title` (str), `start` (datetime), `end`
(datetime), `attendees` (list of str, default empty).
- Creating an event whose `end` is not after its `start` → `ValueError`.
- `duration_minutes()` → int.
- `overlaps(other)` → True if the two time ranges overlap. Ranges are half-open: an event
  ending at 10:00 does **not** overlap one starting at 10:00.
- `shares_attendee(other)` → True if at least one attendee is in both events.

### 4.3 Recurrence (`scheduler/recurrence.py`)
`RecurrenceRule(frequency, interval=1, count=None, until=None)`:
- `frequency` is `"daily"`, `"weekly"` or `"weekdays"`; anything else → `ValueError`.
- `interval` (≥ 1, else `ValueError`) applies to `daily` (every N days) and `weekly`
  (every N weeks). For `weekdays`, `interval` must be 1 (else `ValueError`).
- At least one of `count` (maximum number of occurrences) and `until` (last allowed
  start, inclusive) must be given, else `ValueError`. If both are given, whichever limit
  is reached first wins.
- `occurrences(start)` → list of datetimes, in order:
  - `daily`/`weekly`: `start`, `start + interval`, `start + 2·interval`, …
  - `weekdays`: every Monday–Friday from `start` on, at the time of day of `start`
    (`start` itself counts only if it is a weekday).

### 4.4 Calendar (`scheduler/calendar.py`)
`Calendar()`:
- `add(event)`: duplicate `event_id` → `SchedulerError`. If the event overlaps an existing
  event **and** they share an attendee → `ConflictError` (nothing is added). Events
  without common attendees may overlap.
- `add_recurring(event, rule)` → list of created events. One event per occurrence of
  `rule.occurrences(event.start)`, with ids `"<event_id>#1"`, `"<event_id>#2"`, …, the
  same title, duration and (a copy of the) attendees. All-or-nothing: if any occurrence
  would conflict, none is added and `ConflictError` is raised.
- `get(event_id)`, `remove(event_id)`: unknown id → `UnknownEvent`.
- `events_on(day)` → events starting on that `date`, sorted by start.
- `events_between(start, end)` → events overlapping the half-open range `[start, end)`,
  sorted by start.
- `agenda_for(attendee, day)` → that attendee's events starting on `day`, sorted by start.

### 4.5 Availability (`scheduler/availability.py`)
`free_slots(calendar, attendees, day, day_start=time(9, 0), day_end=time(17, 0),
min_minutes=30)` → list of `(start, end)` datetime pairs, in order: the maximal periods
on `day` between `day_start` and `day_end` in which **none** of the given attendees has
an event, keeping only periods of at least `min_minutes`. Events that only partly fall
inside working hours block the part inside.

### 4.6 Export (`scheduler/export.py`)
Both functions take an iterable of events, output them sorted by start, and join lines
with `"\n"` (no trailing newline).
- `to_csv(events)`: header `id,title,start,end,attendees`; times as `YYYY-MM-DD HH:MM`;
  attendees joined with `;`.
- `to_ics(events)`:
  ```
  BEGIN:VCALENDAR
  BEGIN:VEVENT            (per event)
  UID:<event_id>
  SUMMARY:<title>
  DTSTART:<YYYYMMDDTHHMMSS>
  DTEND:<YYYYMMDDTHHMMSS>
  ATTENDEE:<name>         (one line per attendee, in order)
  END:VEVENT
  END:VCALENDAR
  ```

## 5. Non-functional requirements
- Adding a new recurrence frequency should not require changing the calendar.
- No global mutable state.
