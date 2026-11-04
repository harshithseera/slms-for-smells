from datetime import date

import pytest

from scheduler.calendar import Calendar
from scheduler.errors import ConflictError, SchedulerError, UnknownEvent
from scheduler.recurrence import RecurrenceRule

from helpers import at, ev


def test_add_get_remove():
    cal = Calendar()
    e = ev("a", at(9), at(10))
    cal.add(e)
    assert cal.get("a") is e
    with pytest.raises(SchedulerError):
        cal.add(ev("a", at(11), at(12)))
    cal.remove("a")
    with pytest.raises(UnknownEvent):
        cal.get("a")
    with pytest.raises(UnknownEvent):
        cal.remove("a")


def test_conflict_only_with_shared_attendee():
    cal = Calendar()
    cal.add(ev("a", at(9), at(10), ["ana"]))
    cal.add(ev("b", at(9, 30), at(10, 30), ["ben"]))
    cal.add(ev("c", at(10), at(11), ["ana"]))
    with pytest.raises(ConflictError):
        cal.add(ev("d", at(9, 45), at(10, 15), ["cy", "ana"]))
    with pytest.raises(UnknownEvent):
        cal.get("d")


def test_add_recurring_ids_and_copies():
    cal = Calendar()
    created = cal.add_recurring(ev("su", at(9, 30), at(9, 45), ["ana", "ben"], "Stand-up"),
                                RecurrenceRule("daily", count=3))
    assert [e.event_id for e in created] == ["su#1", "su#2", "su#3"]
    assert all(e.title == "Stand-up" and e.duration_minutes() == 15 for e in created)
    assert created[2].start == at(9, 30, (2026, 3, 4))
    created[0].attendees.append("cy")
    assert created[1].attendees == ["ana", "ben"]


def test_add_recurring_is_all_or_nothing():
    cal = Calendar()
    cal.add(ev("busy", at(9, 30, (2026, 3, 4)), at(10, 0, (2026, 3, 4)), ["ben"]))
    with pytest.raises(ConflictError):
        cal.add_recurring(ev("su", at(9, 30), at(9, 45), ["ana", "ben"]), RecurrenceRule("daily", count=3))
    assert cal.events_between(at(0), at(23, 59, (2026, 3, 9))) == [cal.get("busy")]


def test_queries_sorted():
    cal = Calendar()
    cal.add(ev("late", at(15), at(16), ["ana"]))
    cal.add(ev("early", at(8), at(9), ["ben"]))
    cal.add(ev("tue", at(9, 0, (2026, 3, 3)), at(10, 0, (2026, 3, 3)), ["ana"]))
    cal.add(ev("night", at(23), at(1, 0, (2026, 3, 3)), ["cy"]))
    assert [e.event_id for e in cal.events_on(date(2026, 3, 2))] == ["early", "late", "night"]
    assert [e.event_id for e in cal.events_between(at(8, 30), at(15))] == ["early"]
    assert [e.event_id for e in cal.events_between(at(0, 30, (2026, 3, 3)), at(9, 30, (2026, 3, 3)))] == ["night", "tue"]
    assert [e.event_id for e in cal.agenda_for("ana", date(2026, 3, 2))] == ["late"]
