"""The club: members, trainers, classes, bookings, fees and reports."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from gymdesk import billing, reports
from gymdesk.models import Booking, GymClass, Member, Payment, Trainer
from gymdesk.notifications import booking_email, cancellation_email


class GymClub:
    def __init__(self, name: str) -> None:
        self.name = name
        self.members: dict[str, Member] = {}
        self.trainers: dict[str, Trainer] = {}
        self.classes: dict[str, GymClass] = {}
        self.bookings: dict[str, Booking] = {}
        self.payments: list[Payment] = []
        self.outbox: list[dict] = []
        self.audit_log: list[str] = []
        self._next_booking = 1

    def add_member(self, member: Member) -> None:
        if member.member_id in self.members:
            raise ValueError(f"member {member.member_id} exists")
        self.members[member.member_id] = member
        self.audit(f"member added {member.member_id}")

    def remove_member(self, member_id: str) -> None:
        self.find_member(member_id)
        del self.members[member_id]
        for b in self.bookings.values():
            if b.member_id == member_id:
                b.cancelled = True
        self.audit(f"member removed {member_id}")

    def find_member(self, member_id: str) -> Member:
        try:
            return self.members[member_id]
        except KeyError:
            raise LookupError(f"no member {member_id}") from None

    def upgrade_plan(self, member_id: str, plan: str) -> None:
        billing.monthly_fee(plan)  # validates the plan
        self.find_member(member_id).plan = plan
        self.audit(f"plan {member_id} -> {plan}")

    def add_trainer(self, trainer: Trainer) -> None:
        self.trainers[trainer.trainer_id] = trainer

    def schedule_class(self, class_id: str, title: str, trainer_id: str, start: datetime,
                       duration_min: int, capacity: int, room: str) -> GymClass:
        if trainer_id not in self.trainers:
            raise LookupError(f"no trainer {trainer_id}")
        gc = GymClass(class_id, title, trainer_id, start, duration_min, capacity, room)
        self.classes[class_id] = gc
        return gc

    def book(self, member_id: str, class_id: str, now: datetime) -> Booking:
        member = self.find_member(member_id)
        gc = self.classes[class_id]
        if len(self.attendees(class_id)) >= gc.capacity:
            raise ValueError(f"class {class_id} is full")
        if any(m.member_id == member_id for m in self.attendees(class_id)):
            raise ValueError(f"{member_id} already booked")
        booking = Booking(f"B{self._next_booking}", member_id, class_id, now)
        self._next_booking += 1
        self.bookings[booking.booking_id] = booking
        self.outbox.append(booking_email(member, gc))
        return booking

    def cancel_booking(self, booking_id: str) -> None:
        booking = self.bookings[booking_id]
        booking.cancelled = True
        self.outbox.append(cancellation_email(self.find_member(booking.member_id), self.classes[booking.class_id]))

    def attendees(self, class_id: str) -> list[Member]:
        return [self.members[b.member_id] for b in self.bookings.values()
                if b.class_id == class_id and not b.cancelled and b.member_id in self.members]

    def record_visit(self, member_id: str) -> None:
        self.find_member(member_id).visits += 1

    def charge_monthly_fees(self, today: date) -> float:
        total = 0.0
        for m in self.members.values():
            fee = billing.monthly_fee(m.plan)
            if m.visits > 20:
                fee = round(fee * 0.9, 2)
            m.balance = round(m.balance + fee, 2)
            total += fee
        self.audit(f"fees charged {today.isoformat()}")
        return round(total, 2)

    def record_payment(self, member_id: str, amount: float, today: date) -> float:
        member = self.find_member(member_id)
        member.balance = round(member.balance - amount, 2)
        self.payments.append(Payment(member_id, amount, today))
        return member.balance

    def apply_charge(self, member_id: str, amount: float, refund: bool = False) -> float:
        member = self.find_member(member_id)
        if refund:
            member.balance = round(member.balance - amount, 2)
            self.audit(f"refund {member_id} {amount:.2f}")
        else:
            member.balance = round(member.balance + amount, 2)
            self.audit(f"charge {member_id} {amount:.2f}")
        return member.balance

    def find_by_email(self, email: str) -> Member | None:
        for m in self.members.values():
            if m.email == email:
                return m
        return None

    def member_balance(self, member_id: str) -> float:
        return self.find_member(member_id).balance

    def send_reminders(self, now: datetime, dry_run: bool = False) -> int:
        sent = 0
        for b in self.bookings.values():
            gc = self.classes[b.class_id]
            if not b.cancelled and now <= gc.start <= now + timedelta(hours=24):
                if not dry_run:
                    self.outbox.append(booking_email(self.members[b.member_id], gc))
                sent += 1
        return sent

    def monthly_report(self, today: date) -> list[str]:
        return reports.MonthlyReport(self).lines(today)

    def export_members_csv(self) -> str:
        rows = ["member_id,name,email,plan,visits,balance"]
        for m in self.members.values():
            rows.append(f"{m.member_id},{m.first_name} {m.last_name},{m.email},{m.plan},{m.visits},{m.balance:.2f}")
        return "\n".join(rows)

    def audit(self, message: str) -> None:
        self.audit_log.append(message)
