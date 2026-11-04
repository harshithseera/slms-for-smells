from datetime import datetime

from gymdesk.models import GymClass, Trainer
from gymdesk.scheduling import Scheduler

from conftest import MON

T = {"t1": Trainer("t1", "Cara", ["Yoga"], max_classes_per_week=2), "t2": Trainer("t2", "Dev", [])}


def gc(cid, day, hour, trainer="t1", room="A", cap=10, title="Yoga", minutes=60):
    return GymClass(cid, title, trainer, datetime(2026, 3, day, hour), minutes, cap, room)


def test_plan_week_accepts_and_warns():
    s = Scheduler({"A": 12, "B": 20})
    accepted, warnings = s.plan_week([
        gc("ok1", 2, 9),
        gc("roomclash", 2, 9, trainer="t2"),
        gc("trainerclash", 2, 9, room="B"),
        gc("capped", 3, 9, cap=30),
        gc("limit", 4, 9),
        gc("noroom", 4, 11, trainer="t2", room="Z"),
        gc("notrainer", 4, 12, trainer="t9"),
        gc("late", 10, 9, trainer="t2"),
        gc("odd", 5, 9, trainer="t2", title="Boxing"),
    ], T, MON)
    assert [c.class_id for c in accepted] == ["ok1", "capped", "odd"]
    assert accepted[1].capacity == 12
    assert warnings == [
        "roomclash: room A taken by ok1",
        "trainerclash: trainer Cara double-booked",
        "capped: capacity 30 > room 12, capped",
        "limit: trainer Cara over weekly limit",
        "noroom: unknown room Z",
        "notrainer: unknown trainer t9",
        "late: outside week",
    ]


def test_specialty_warning():
    s = Scheduler({"A": 12})
    accepted, warnings = s.plan_week([gc("p", 2, 9, title="Spin")], T, MON)
    assert [c.class_id for c in accepted] == ["p"] and warnings == ["p: Cara does not usually teach Spin"]
