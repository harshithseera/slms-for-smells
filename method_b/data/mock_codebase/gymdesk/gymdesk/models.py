"""Plain data records used across gymdesk."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Member:
    member_id: str
    first_name: str
    last_name: str
    email: str
    plan: str  # "basic" | "plus" | "premium"
    joined: date
    visits: int = 0
    balance: float = 0.0


@dataclass
class Trainer:
    trainer_id: str
    name: str
    specialties: list[str] = field(default_factory=list)
    max_classes_per_week: int = 10


@dataclass
class GymClass:
    class_id: str
    title: str
    trainer_id: str
    start: datetime
    duration_min: int
    capacity: int
    room: str


@dataclass
class Booking:
    booking_id: str
    member_id: str
    class_id: str
    booked_at: datetime
    cancelled: bool = False


@dataclass
class Payment:
    member_id: str
    amount: float
    paid_on: date
    method: str = "card"
