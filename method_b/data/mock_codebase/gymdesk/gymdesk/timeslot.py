"""Time-range arithmetic for class slots."""
from __future__ import annotations

from datetime import datetime, timedelta


class TimeSlot:
    """A half-open time range [start, end)."""

    def __init__(self, start: datetime, end: datetime) -> None:
        if end <= start:
            raise ValueError("slot must end after it starts")
        self.start = start
        self.end = end

    @classmethod
    def of(cls, start: datetime, minutes: int) -> TimeSlot:
        return cls(start, start + timedelta(minutes=minutes))

    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    def overlaps(self, other: TimeSlot) -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    def covers(self, other: TimeSlot) -> bool:
        return self.start <= other.start and other.end <= self.end

    def shift(self, minutes: int) -> TimeSlot:
        d = timedelta(minutes=minutes)
        return TimeSlot(self.start + d, self.end + d)

    def extend(self, minutes: int) -> TimeSlot:
        return TimeSlot(self.start, self.end + timedelta(minutes=minutes))

    def split(self, minutes: int) -> tuple[TimeSlot, TimeSlot]:
        cut = self.start + timedelta(minutes=minutes)
        if not self.contains(cut) or cut == self.start:
            raise ValueError("cut point outside slot")
        return TimeSlot(self.start, cut), TimeSlot(cut, self.end)

    def merge(self, other: TimeSlot) -> TimeSlot:
        if not (self.overlaps(other) or self.touches(other)):
            raise ValueError("slots are disjoint")
        return TimeSlot(min(self.start, other.start), max(self.end, other.end))

    def touches(self, other: TimeSlot) -> bool:
        return self.end == other.start or other.end == self.start

    def gap_to(self, other: TimeSlot) -> int:
        if self.overlaps(other):
            return 0
        later, earlier = (other, self) if other.start >= self.end else (self, other)
        return int((later.start - earlier.end).total_seconds() // 60)

    def same_day(self) -> bool:
        return self.start.date() == (self.end - timedelta(microseconds=1)).date()

    def starts_before(self, other: TimeSlot) -> bool:
        return self.start < other.start

    def ends_after(self, other: TimeSlot) -> bool:
        return self.end > other.end

    def intersection(self, other: TimeSlot) -> TimeSlot | None:
        if not self.overlaps(other):
            return None
        return TimeSlot(max(self.start, other.start), min(self.end, other.end))

    def as_tuple(self) -> tuple[datetime, datetime]:
        return self.start, self.end

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TimeSlot) and self.as_tuple() == other.as_tuple()

    def __repr__(self) -> str:
        return f"TimeSlot({self.start:%Y-%m-%d %H:%M}, {self.minutes()} min)"
