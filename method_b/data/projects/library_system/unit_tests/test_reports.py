from datetime import date

from library.reports import member_summary, overdue_report

from conftest import D0, DUNE, EMMA


def test_overdue_report_format(service):
    service.checkout("m1", DUNE, D0)
    service.checkout("m2", EMMA, date(2026, 1, 2))
    assert overdue_report(service, date(2026, 1, 18)) == [
        "Ada Lovelace | Dune | 3 days | 0.75",
        "Alan Turing | Emma | 2 days | 0.50",
    ]
    assert overdue_report(service, date(2026, 1, 10)) == []


def test_member_summary(service):
    service.checkout("m1", DUNE, D0)
    service.checkout("m1", EMMA, date(2026, 1, 10))
    service.return_book("m1", DUNE, date(2026, 1, 17))  # 0.50 charged
    service.checkout("m1", DUNE, date(2026, 1, 2))  # due 01-16 -> 4 days late on 01-20 = 1.00
    s = member_summary(service, "m1", date(2026, 1, 20))
    assert s == {"member_id": "m1", "name": "Ada Lovelace", "active_loans": 2, "overdue": 1,
                 "balance": 0.5, "accrued_fines": 1.0}
