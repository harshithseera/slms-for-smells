from datetime import date, datetime

import pytest

from gymdesk.billing import compute_late_fee, invoice_total, monthly_fee
from gymdesk.models import GymClass, Member, Payment
from gymdesk.notifications import booking_email, cancellation_email
from gymdesk.reports import revenue_for_member
from gymdesk.stats import geometric_mean_session_minutes, mean_session_minutes, occupancy
from gymdesk.timeslot import TimeSlot


def test_billing():
    assert monthly_fee("premium") == 79.0
    with pytest.raises(ValueError):
        monthly_fee("gold")
    pays = [Payment("m", 100.0, date(2026, 1, 1)), Payment("m", -5.0, date(2026, 1, 2))]
    assert invoice_total(pays, 0.1, 0.2) == 108.0
    assert revenue_for_member(pays, 0.1, 0.2) == 108.0
    fee = compute_late_fee("m", 50.0, date(2026, 1, 1), date(2026, 1, 11), 0.01, 3, 5.0, "EUR")
    assert fee == {"member_id": "m", "fee": 3.5, "currency": "EUR"}
    assert compute_late_fee("m", 50.0, date(2026, 1, 1), date(2026, 1, 3), 0.01, 3, 5.0, "EUR")["fee"] == 0.0


def test_stats():
    assert mean_session_minutes([30, 60, 90]) == 60.0
    assert geometric_mean_session_minutes([10, 1000]) == pytest.approx(100.0)
    assert mean_session_minutes([]) == 0.0 and occupancy(3, 12) == 0.25 and occupancy(1, 0) == 0.0


def test_emails():
    m = Member("m1", "Ana", "Lima", "ana@x.org", "plus", date(2025, 1, 1))
    g = GymClass("c", "Spin", "t", datetime(2026, 3, 3, 18), 45, 10, "Room 2")
    assert booking_email(m, g)["body"].splitlines()[2] == "You are booked for Spin on Tue 03 Mar 18:00 in Room 2."
    assert cancellation_email(m, g)["subject"] == "Cancelled: Spin"


def test_timeslot():
    a = TimeSlot.of(datetime(2026, 3, 2, 9), 60)
    b = TimeSlot.of(datetime(2026, 3, 2, 9, 30), 60)
    c = TimeSlot.of(datetime(2026, 3, 2, 11), 30)
    assert a.overlaps(b) and not a.overlaps(c) and a.gap_to(c) == 60
    assert a.merge(b).minutes() == 90 and a.intersection(b).minutes() == 30
    left, right = a.split(15)
    assert left.minutes() == 15 and right.minutes() == 45 and left.touches(right)
    assert a.shift(30) == b and a.extend(30).covers(b) and a.same_day()
    with pytest.raises(ValueError):
        TimeSlot(a.end, a.start)
