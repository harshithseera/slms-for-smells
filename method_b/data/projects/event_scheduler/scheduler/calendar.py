"""The team calendar: storage, conflict checks and queries."""
from __future__ import annotations

from datetime import date, datetime

from scheduler.errors import ConflictError, SchedulerError, UnknownEvent
from scheduler.events import Event
from scheduler.recurrence import RecurrenceRule


class Calendar:
    def __init__(self) -> None:
        self._events: dict[str, Event] = {}

    def _check(self, new: list[Event]) -> None:
        for event in new:
            if event.event_id in self._events:
                raise SchedulerError(f"duplicate event id {event.event_id}")
            for other in self._events.values():
                if event.overlaps(other) and event.shares_attendee(other):
                    raise ConflictError(f"{event.event_id} conflicts with {other.event_id}")

    def add(self, event: Event) -> None:
        self._check([event])
        self._events[event.event_id] = event

    def add_recurring(self, event: Event, rule: RecurrenceRule) -> list[Event]:
        duration = event.end - event.start
        created = [
            Event(f"{event.event_id}#{i}", event.title, when, when + duration, list(event.attendees))
            for i, when in enumerate(rule.occurrences(event.start), start=1)
        ]
        self._check(created)
        for e in created:
            self._events[e.event_id] = e
        return created

    def get(self, event_id: str) -> Event:
        try:
            return self._events[event_id]
        except KeyError:
            raise UnknownEvent(event_id) from None

    def remove(self, event_id: str) -> None:
        self.get(event_id)
        del self._events[event_id]

    def _sorted(self, events) -> list[Event]:
        return sorted(events, key=lambda e: e.start)

    def events_on(self, day: date) -> list[Event]:
        return self._sorted(e for e in self._events.values() if e.start.date() == day)

    def events_between(self, start: datetime, end: datetime) -> list[Event]:
        return self._sorted(e for e in self._events.values() if e.start < end and start < e.end)

    def agenda_for(self, attendee: str, day: date) -> list[Event]:
        return [e for e in self.events_on(day) if attendee in e.attendees]
