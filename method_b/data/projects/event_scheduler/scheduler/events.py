"""Calendar events."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    event_id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("an event must end after it starts")

    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    def overlaps(self, other: Event) -> bool:
        return self.start < other.end and other.start < self.end

    def shares_attendee(self, other: Event) -> bool:
        return bool(set(self.attendees) & set(other.attendees))
