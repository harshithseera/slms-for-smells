"""E-mails sent to members."""
from __future__ import annotations

from gymdesk.models import GymClass, Member


def booking_email(member: Member, gym_class: GymClass) -> dict:
    subject = f"Booked: {gym_class.title}"
    when = gym_class.start.strftime("%a %d %b %H:%M")
    lines = [f"Hi {member.first_name},", "",
             f"You are booked for {gym_class.title} on {when} in {gym_class.room}.", "",
             "See you there!", "gymdesk"]
    body = "\n".join(lines)
    return {"to": member.email, "subject": subject, "body": body}


def cancellation_email(member: Member, gym_class: GymClass) -> dict:
    subject = f"Cancelled: {gym_class.title}"
    when = gym_class.start.strftime("%a %d %b %H:%M")
    lines = [f"Hi {member.first_name},", "",
             f"Your booking for {gym_class.title} on {when} in {gym_class.room} is cancelled.", "",
             "Hope to see you soon!", "gymdesk"]
    body = "\n".join(lines)
    return {"to": member.email, "subject": subject, "body": body}
