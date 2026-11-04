from datetime import datetime

import pytest

from scheduler.recurrence import RecurrenceRule

from helpers import at


def test_daily_and_weekly_with_interval():
    assert RecurrenceRule("daily", count=3).occurrences(at(9)) == [
        datetime(2026, 3, 2, 9), datetime(2026, 3, 3, 9), datetime(2026, 3, 4, 9)]
    assert RecurrenceRule("weekly", interval=2, count=3).occurrences(at(9)) == [
        datetime(2026, 3, 2, 9), datetime(2026, 3, 16, 9), datetime(2026, 3, 30, 9)]


def test_weekdays_skip_weekends():
    fri = datetime(2026, 3, 6, 9, 30)
    days = [d.day for d in RecurrenceRule("weekdays", count=4).occurrences(fri)]
    assert days == [6, 9, 10, 11]
    sat = datetime(2026, 3, 7, 9, 30)
    assert RecurrenceRule("weekdays", count=1).occurrences(sat) == [datetime(2026, 3, 9, 9, 30)]


def test_until_is_inclusive_and_first_limit_wins():
    until = datetime(2026, 3, 4, 9)
    assert len(RecurrenceRule("daily", until=until).occurrences(at(9))) == 3
    assert len(RecurrenceRule("daily", count=2, until=until).occurrences(at(9))) == 2
    assert len(RecurrenceRule("daily", count=10, until=until).occurrences(at(9))) == 3


@pytest.mark.parametrize("kwargs", [
    {"frequency": "hourly", "count": 1},
    {"frequency": "daily", "interval": 0, "count": 1},
    {"frequency": "weekdays", "interval": 2, "count": 1},
    {"frequency": "daily"},
])
def test_invalid_rules(kwargs):
    with pytest.raises(ValueError):
        RecurrenceRule(**kwargs)
