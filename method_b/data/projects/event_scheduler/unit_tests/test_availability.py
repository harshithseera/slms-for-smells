from datetime import date, time

from scheduler.availability import free_slots
from scheduler.calendar import Calendar

from helpers import at, ev

DAY = date(2026, 3, 2)


def test_empty_day_is_one_slot():
    assert free_slots(Calendar(), ["ana"], DAY) == [(at(9), at(17))]


def test_gaps_across_attendees_with_min_length():
    cal = Calendar()
    cal.add(ev("a1", at(8), at(9, 30), ["ana"]))      # partly before working hours
    cal.add(ev("b1", at(10), at(11), ["ben"]))
    cal.add(ev("a2", at(10, 30), at(12), ["ana"]))    # overlaps ben's meeting
    cal.add(ev("b2", at(12, 20), at(13), ["ben"]))    # leaves a 20-minute gap
    cal.add(ev("c1", at(14), at(15), ["cy"]))         # not one of the attendees
    cal.add(ev("a3", at(16, 30), at(18), ["ana"]))    # partly after working hours
    assert free_slots(cal, ["ana", "ben"], DAY) == [(at(9, 30), at(10)), (at(13), at(16, 30))]
    assert free_slots(cal, ["ana", "ben"], DAY, min_minutes=15) == [
        (at(9, 30), at(10)), (at(12), at(12, 20)), (at(13), at(16, 30))]


def test_custom_working_hours():
    cal = Calendar()
    cal.add(ev("a", at(12), at(13), ["ana"]))
    assert free_slots(cal, ["ana"], DAY, day_start=time(11), day_end=time(14), min_minutes=60) == [
        (at(11), at(12)), (at(13), at(14))]
