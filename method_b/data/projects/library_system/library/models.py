"""Plain data model: books, members and loans."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Book:
    isbn: str
    title: str
    author: str
    year: int
    copies: int = 1


@dataclass
class Member:
    member_id: str
    name: str
    email: str
    max_loans: int = 3


@dataclass
class Loan:
    isbn: str
    member_id: str
    loan_date: date
    due_date: date
    returned_date: date | None = None

    def is_returned(self) -> bool:
        return self.returned_date is not None

    def days_overdue(self, today: date) -> int:
        end = self.returned_date or today
        return max(0, (end - self.due_date).days)

    def is_overdue(self, today: date) -> bool:
        return not self.is_returned() and self.due_date < today
