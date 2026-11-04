from datetime import date

import pytest

from library.errors import BookUnavailable, LibraryError, LoanLimitExceeded, NotOnLoan, UnknownMember
from library.fines import FinePolicy
from library.loans import LoanService
from library.models import Member

from conftest import D0, DUNE, EMMA


def test_default_policy_and_public_attributes(catalog):
    s = LoanService(catalog)
    assert s.catalog is catalog and isinstance(s.fine_policy, FinePolicy)


def test_register_duplicate_member(service):
    with pytest.raises(LibraryError):
        service.register_member(Member("m1", "Other", "o@example.org"))
    with pytest.raises(UnknownMember):
        service.get_member("zz")


def test_checkout_sets_dates_and_takes_copy(service):
    loan = service.checkout("m1", DUNE, D0)
    assert loan.loan_date == D0 and loan.due_date == date(2026, 1, 15)
    assert service.catalog.available_copies(DUNE) == 1
    assert service.active_loans("m1") == [loan]


def test_custom_loan_period(catalog):
    s = LoanService(catalog, loan_period_days=7)
    s.register_member(Member("m", "M", "m@x"))
    assert s.checkout("m", EMMA, D0).due_date == date(2026, 1, 8)


def test_checkout_errors(service):
    with pytest.raises(UnknownMember):
        service.checkout("zz", DUNE, D0)
    service.checkout("m2", DUNE, D0)
    with pytest.raises(LoanLimitExceeded):
        service.checkout("m2", EMMA, D0)
    service.checkout("m1", EMMA, D0)
    with pytest.raises(BookUnavailable):
        service.checkout("m1", EMMA, D0)


def test_return_on_time_and_late(service):
    service.checkout("m1", DUNE, D0)
    service.checkout("m1", EMMA, D0)
    assert service.return_book("m1", DUNE, date(2026, 1, 15)) == 0.0
    assert service.return_book("m1", EMMA, date(2026, 1, 19)) == 1.0
    assert service.balance("m1") == 1.0
    assert service.active_loans("m1") == []
    assert service.catalog.available_copies(DUNE) == 2


def test_return_without_loan(service):
    with pytest.raises(NotOnLoan):
        service.return_book("m1", DUNE, D0)


def test_pay(service):
    service.checkout("m1", DUNE, D0)
    service.return_book("m1", DUNE, date(2026, 1, 25))  # 10 days -> 2.50
    assert service.pay("m1", 1.0) == 1.5
    assert service.pay("m1", 5.0) == 0.0
    assert service.balance("m1") == 0.0
    with pytest.raises(ValueError):
        service.pay("m1", 0)


def test_overdue_loans_sorted_by_due_date(service):
    late = service.checkout("m2", DUNE, D0)
    later = service.checkout("m1", EMMA, date(2026, 1, 3))
    service.checkout("m1", DUNE, date(2026, 1, 20))
    assert service.overdue_loans(date(2026, 1, 25)) == [late, later]
