"""Front-desk reports built on top of LoanService."""
from __future__ import annotations

from datetime import date

from library.loans import LoanService


def overdue_report(service: LoanService, today: date) -> list[str]:
    lines = []
    for loan in service.overdue_loans(today):
        member = service.get_member(loan.member_id)
        book = service.catalog.get(loan.isbn)
        fine = service.fine_policy.fine_for(loan, today)
        lines.append(f"{member.name} | {book.title} | {loan.days_overdue(today)} days | {fine:.2f}")
    return lines


def member_summary(service: LoanService, member_id: str, today: date) -> dict:
    member = service.get_member(member_id)
    active = service.active_loans(member_id)
    overdue = [l for l in active if l.is_overdue(today)]
    accrued = round(sum(service.fine_policy.fine_for(l, today) for l in overdue), 2)
    return {
        "member_id": member.member_id,
        "name": member.name,
        "active_loans": len(active),
        "overdue": len(overdue),
        "balance": service.balance(member_id),
        "accrued_fines": accrued,
    }
