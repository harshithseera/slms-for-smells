"""Fine policy for late returns."""
from __future__ import annotations

from datetime import date

from library.models import Loan


class FinePolicy:
    def __init__(self, daily_rate: float = 0.25, grace_days: int = 0, max_fine: float = 10.0) -> None:
        self.daily_rate = daily_rate
        self.grace_days = grace_days
        self.max_fine = max_fine

    def fine_for(self, loan: Loan, today: date) -> float:
        days = loan.days_overdue(today) - self.grace_days
        if days <= 0:
            return 0.0
        return round(min(days * self.daily_rate, self.max_fine), 2)
