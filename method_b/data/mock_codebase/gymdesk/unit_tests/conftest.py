from datetime import date, datetime

import pytest

from gymdesk.club import GymClub
from gymdesk.models import Member, Trainer

MON = datetime(2026, 3, 2, 0, 0)  # a Monday


@pytest.fixture
def club():
    c = GymClub("Northside")
    c.add_member(Member("m1", "Ana", "Lima", "ana@x.org", "plus", date(2025, 3, 1), visits=12))
    c.add_member(Member("m2", "Ben", "Okafor", "ben@x.org", "basic", date(2026, 1, 1)))
    c.add_trainer(Trainer("t1", "Cara", ["Yoga", "Pilates"], max_classes_per_week=2))
    c.schedule_class("c1", "Yoga", "t1", datetime(2026, 3, 3, 18, 0), 60, 2, "Studio A")
    return c
