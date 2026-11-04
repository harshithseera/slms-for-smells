"""Front-desk check-in helpers."""
from __future__ import annotations

from gymdesk.club import GymClub
from gymdesk.models import GymClass


class CheckInDesk:
    def __init__(self, club: GymClub) -> None:
        self.club = club

    def room_for(self, booking_id: str) -> str:
        return self.club.classes[self.club.bookings[booking_id].class_id].room

    def trainer_name_for(self, booking_id: str) -> str:
        return self.club.trainers[self.club.classes[self.club.bookings[booking_id].class_id].trainer_id].name

    def check_in(self, booking_id: str) -> str:
        booking = self.club.bookings[booking_id]
        if booking.cancelled:
            raise ValueError(f"booking {booking_id} is cancelled")
        self.club.record_visit(booking.member_id)
        return f"{self.room_for(booking_id)} with {self.trainer_name_for(booking_id)}"


def class_day(gym_class: GymClass) -> str:
    return gym_class.start.date().isoformat()


def normalise_email(email: str) -> str:
    return email.strip().lower()


def email_domain(email: str) -> str:
    return email.strip().lower().split("@")[1]
