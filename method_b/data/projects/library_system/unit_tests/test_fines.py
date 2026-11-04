from datetime import date

from library.fines import FinePolicy
from library.models import Loan

DUE = date(2026, 1, 15)


def loan(returned=None):
    return Loan("x", "m1", date(2026, 1, 1), DUE, returned)


def test_loan_overdue_days():
    assert loan().days_overdue(date(2026, 1, 15)) == 0
    assert loan().days_overdue(date(2026, 1, 10)) == 0
    assert loan().days_overdue(date(2026, 1, 18)) == 3
    assert loan(returned=date(2026, 1, 16)).days_overdue(date(2026, 2, 1)) == 1


def test_loan_is_overdue_only_when_not_returned():
    assert not loan().is_overdue(DUE)
    assert loan().is_overdue(date(2026, 1, 16))
    assert not loan(returned=date(2026, 1, 20)).is_overdue(date(2026, 1, 25))


def test_default_fine():
    p = FinePolicy()
    assert p.fine_for(loan(), date(2026, 1, 15)) == 0.0
    assert p.fine_for(loan(), date(2026, 1, 18)) == 0.75


def test_grace_days_and_cap():
    assert FinePolicy(grace_days=2).fine_for(loan(), date(2026, 1, 17)) == 0.0
    assert FinePolicy(grace_days=2).fine_for(loan(), date(2026, 1, 18)) == 0.25
    assert FinePolicy(daily_rate=1.0, max_fine=5.0).fine_for(loan(), date(2026, 3, 1)) == 5.0
