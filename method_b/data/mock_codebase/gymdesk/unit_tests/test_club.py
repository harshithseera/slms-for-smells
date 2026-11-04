from datetime import date, datetime

import pytest

from gymdesk.models import Member


def test_booking_flow_and_emails(club):
    b = club.book("m1", "c1", datetime(2026, 3, 1, 9))
    assert b.booking_id == "B1" and [m.member_id for m in club.attendees("c1")] == ["m1"]
    assert club.outbox[-1]["subject"] == "Booked: Yoga" and club.outbox[-1]["to"] == "ana@x.org"
    with pytest.raises(ValueError):
        club.book("m1", "c1", datetime(2026, 3, 1, 9))
    club.cancel_booking("B1")
    assert club.attendees("c1") == [] and club.outbox[-1]["subject"] == "Cancelled: Yoga"


def test_capacity(club):
    club.add_member(Member("m3", "Cy", "Dutt", "cy@x.org", "basic", date(2026, 2, 1)))
    club.book("m1", "c1", datetime(2026, 3, 1))
    club.book("m2", "c1", datetime(2026, 3, 1))
    with pytest.raises(ValueError):
        club.book("m3", "c1", datetime(2026, 3, 1))


def test_members(club):
    with pytest.raises(ValueError):
        club.add_member(Member("m1", "X", "Y", "x@y", "basic", date(2026, 1, 1)))
    club.upgrade_plan("m2", "premium")
    assert club.find_member("m2").plan == "premium"
    with pytest.raises(ValueError):
        club.upgrade_plan("m2", "gold")
    club.book("m2", "c1", datetime(2026, 3, 1))
    club.remove_member("m2")
    with pytest.raises(LookupError):
        club.find_member("m2")
    assert club.attendees("c1") == []


def test_fees_and_payments(club):
    assert club.charge_monthly_fees(date(2026, 3, 1)) == 78.0
    assert club.member_balance("m1") == 49.0
    assert club.record_payment("m1", 20.0, date(2026, 3, 2)) == 29.0
    assert len(club.payments) == 1


def test_reminders(club):
    club.book("m1", "c1", datetime(2026, 3, 1))
    assert club.send_reminders(datetime(2026, 3, 3, 9)) == 1
    assert club.send_reminders(datetime(2026, 3, 1, 9)) == 0


def test_export_and_report(club):
    club.record_visit("m2")
    club.record_payment("m1", 30.0, date(2026, 3, 2))
    csv = club.export_members_csv().splitlines()
    assert csv[0] == "member_id,name,email,plan,visits,balance"
    assert csv[2] == "m2,Ben Okafor,ben@x.org,basic,1,0.00"
    lines = club.monthly_report(date(2026, 3, 15))
    assert lines[0] == "Northside monthly report"
    assert lines[1] == "m1,Ana Lima,plus,12,-30.00,13.0"
    assert lines[2] == "m2,Ben Okafor,basic,1,0.00,2.0"
    assert lines[-1] == "revenue,30.00"
