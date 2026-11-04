"""Monthly management report."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from gymdesk import club as club_module
from gymdesk.models import Member, Payment


class MonthlyReport:
    def __init__(self, club: club_module.GymClub) -> None:
        self.club = club
        self.title = f"{club.name} monthly report"

    def loyalty_score(self, member: Member, today: date) -> float:
        months = (today.year - member.joined.year) * 12 + today.month - member.joined.month
        tier_bonus = {"basic": 0, "plus": 5, "premium": 10}[member.plan]
        visit_rate = member.visits / max(months, 1)
        penalty = 5 if member.balance > 0 else 0
        return round(months * 0.5 + visit_rate * 2 + tier_bonus - penalty, 1)

    def member_row(self, member: Member) -> str:
        return (f"{member.member_id},{member.first_name} {member.last_name},"
                f"{member.plan},{member.visits},{member.balance:.2f}")

    def lines(self, today: date) -> list[str]:
        out = [self.title]
        for m in sorted(self.club.members.values(), key=lambda x: x.member_id):
            out.append(f"{self.member_row(m)},{self.loyalty_score(m, today)}")
        out.append(f"revenue,{revenue_for_member(self.club.payments, 0.0, 0.0):.2f}")
        return out


def revenue_for_member(payments: list[Payment], rebate: float, vat: float) -> float:
    acc = 0.0
    for p in payments:
        if p.amount <= 0:
            continue
        acc += p.amount * (1 - rebate)
    acc = acc * (1 + vat)
    return round(acc, 2)


def report_filename(path: str) -> str:
    return Path(path).expanduser().resolve().name
