import pytest

from helpers import at, ev


def test_invalid_range():
    with pytest.raises(ValueError):
        ev("x", at(10), at(10))
    with pytest.raises(ValueError):
        ev("x", at(11), at(10))


def test_duration_and_default_attendees():
    from scheduler.events import Event
    e = Event("a", "A", at(9), at(10, 30))
    assert e.duration_minutes() == 90 and e.attendees == []


def test_overlap_is_half_open():
    a = ev("a", at(9), at(10))
    assert not a.overlaps(ev("b", at(10), at(11)))
    assert a.overlaps(ev("c", at(9, 59), at(11)))
    assert ev("d", at(8), at(12)).overlaps(a)


def test_shares_attendee():
    a = ev("a", at(9), at(10), ["ana", "ben"])
    assert a.shares_attendee(ev("b", at(9), at(10), ["ben"]))
    assert not a.shares_attendee(ev("c", at(9), at(10), ["cy"]))
