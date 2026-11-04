"""Members, checkouts, returns and balances."""
from __future__ import annotations

from datetime import date, timedelta

from library.catalog import Catalog
from library.errors import LibraryError, LoanLimitExceeded, NotOnLoan, UnknownMember
from library.fines import FinePolicy
from library.models import Loan, Member


class LoanService:
    def __init__(self, catalog: Catalog, fine_policy: FinePolicy | None = None, loan_period_days: int = 14) -> None:
        self.catalog = catalog
        self.fine_policy = fine_policy or FinePolicy()
        self.loan_period_days = loan_period_days
        self._members: dict[str, Member] = {}
        self._loans: list[Loan] = []
        self._balances: dict[str, float] = {}

    def register_member(self, member: Member) -> None:
        if member.member_id in self._members:
            raise LibraryError(f"member {member.member_id} already registered")
        self._members[member.member_id] = member
        self._balances[member.member_id] = 0.0

    def get_member(self, member_id: str) -> Member:
        try:
            return self._members[member_id]
        except KeyError:
            raise UnknownMember(member_id) from None

    def checkout(self, member_id: str, isbn: str, today: date) -> Loan:
        member = self.get_member(member_id)
        if len(self.active_loans(member_id)) >= member.max_loans:
            raise LoanLimitExceeded(member_id)
        self.catalog.take_copy(isbn)
        loan = Loan(isbn, member_id, today, today + timedelta(days=self.loan_period_days))
        self._loans.append(loan)
        return loan

    def return_book(self, member_id: str, isbn: str, today: date) -> float:
        loan = next((l for l in self.active_loans(member_id) if l.isbn == isbn), None)
        if loan is None:
            raise NotOnLoan(f"{member_id} has no active loan of {isbn}")
        loan.returned_date = today
        self.catalog.return_copy(isbn)
        fine = self.fine_policy.fine_for(loan, today)
        self._balances[member_id] = round(self._balances[member_id] + fine, 2)
        return fine

    def active_loans(self, member_id: str) -> list[Loan]:
        return [l for l in self._loans if l.member_id == member_id and not l.is_returned()]

    def overdue_loans(self, today: date) -> list[Loan]:
        return sorted((l for l in self._loans if l.is_overdue(today)), key=lambda l: l.due_date)

    def balance(self, member_id: str) -> float:
        self.get_member(member_id)
        return self._balances[member_id]

    def pay(self, member_id: str, amount: float) -> float:
        if amount <= 0:
            raise ValueError("amount must be positive")
        remaining = max(0.0, round(self.balance(member_id) - amount, 2))
        self._balances[member_id] = remaining
        return remaining
