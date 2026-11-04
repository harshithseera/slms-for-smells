from datetime import date, datetime

import pytest

from gymdesk.billing import compute_late_fee, convert_amount, days_overdue, format_amount
from gymdesk.checkin import CheckInDesk, class_day, email_domain, normalise_email
from gymdesk.models import GymClass, Member
from gymdesk.reports import report_filename
from gymdesk.scheduling import Scheduler
from gymdesk.stats import session_summary


def test_loyalty_discount_on_fees(club):
    club.find_member("m1").visits = 25
    assert club.charge_monthly_fees(date(2026, 3, 1)) == 73.1   # 49 * 0.9 + 29
    assert club.member_balance("m1") == 44.1


def test_apply_charge_and_refund(club):
    assert club.apply_charge("m1", 10.0) == 10.0
    assert club.apply_charge("m1", 4.0, refund=True) == 6.0
    assert club.audit_log[-1] == "refund m1 4.00"


def test_find_by_email_and_dry_run(club):
    assert club.find_by_email("ben@x.org").member_id == "m2" and club.find_by_email("x@y") is None
    club.book("m1", "c1", datetime(2026, 3, 1))
    before = len(club.outbox)
    assert club.send_reminders(datetime(2026, 3, 3, 9), dry_run=True) == 1 and len(club.outbox) == before


def test_money_helpers():
    assert format_amount(3.456, " eur ") == "3.46 EUR"
    assert convert_amount(100.0, "EUR", "usd") == 108.0
    with pytest.raises(ValueError):
        format_amount(1.0, "JPY")
    assert days_overdue(date(2026, 1, 1), date(2026, 1, 11), 3) == 7
    assert compute_late_fee("m", 50.0, date(2026, 1, 1), date(2026, 1, 11), 0.01, 3, 5.0, "EUR")["fee"] == 3.5


def test_room_free():
    s = Scheduler({"A": 10})
    busy = [GymClass("x", "Yoga", "t1", datetime(2026, 3, 2, 9), 60, 10, "A")]
    assert not s.room_free("A", datetime(2026, 3, 2, 9, 30), 30, busy)
    assert s.room_free("A", datetime(2026, 3, 2, 10), 30, busy) and s.room_free("B", datetime(2026, 3, 2, 9), 30, busy)


def test_session_summary():
    assert session_summary([30, 90]) == {"count": 2, "mean": 60.0, "longest": 90}
    assert session_summary([30, 90], as_text=True) == "2 sessions, mean 60.0 min, longest 90 min"


def test_check_in(club):
    b = club.book("m2", "c1", datetime(2026, 3, 1))
    desk = CheckInDesk(club)
    assert desk.check_in(b.booking_id) == "Studio A with Cara"
    assert club.find_member("m2").visits == 1
    assert class_day(club.classes["c1"]) == "2026-03-03"
    club.cancel_booking(b.booking_id)
    with pytest.raises(ValueError):
        desk.check_in(b.booking_id)


def test_email_helpers_and_filename():
    assert normalise_email("  Ana@X.org ") == "ana@x.org" and email_domain(" Ana@X.org") == "x.org"
    assert report_filename("~/reports/march.csv") == "march.csv"
