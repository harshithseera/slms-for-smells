from datetime import datetime

from scheduler.events import Event

MON = (2026, 3, 2)  # a Monday


def at(h, m=0, day=MON):
    return datetime(*day, h, m)


def ev(eid, start, end, people=("ana",), title=None):
    return Event(eid, title or eid, start, end, list(people))
