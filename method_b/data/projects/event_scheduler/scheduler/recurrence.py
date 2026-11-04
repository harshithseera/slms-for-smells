"""Recurrence rules for repeating events."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

_STEPS = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}


def _fixed_steps(start: datetime, step: timedelta) -> Iterator[datetime]:
    current = start
    while True:
        yield current
        current += step


def _weekdays(start: datetime) -> Iterator[datetime]:
    current = start
    while True:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


class RecurrenceRule:
    def __init__(self, frequency: str, interval: int = 1, count: int | None = None,
                 until: datetime | None = None) -> None:
        if frequency not in (*_STEPS, "weekdays"):
            raise ValueError(f"unknown frequency {frequency!r}")
        if interval < 1 or (frequency == "weekdays" and interval != 1):
            raise ValueError("invalid interval")
        if count is None and until is None:
            raise ValueError("a rule needs count or until")
        self.frequency = frequency
        self.interval = interval
        self.count = count
        self.until = until

    def _candidates(self, start: datetime) -> Iterator[datetime]:
        if self.frequency == "weekdays":
            return _weekdays(start)
        return _fixed_steps(start, _STEPS[self.frequency] * self.interval)

    def occurrences(self, start: datetime) -> list[datetime]:
        out: list[datetime] = []
        for when in self._candidates(start):
            if (self.count is not None and len(out) >= self.count) or (self.until is not None and when > self.until):
                break
            out.append(when)
        return out
