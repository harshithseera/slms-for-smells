"""Exceptions raised by the scheduler package."""


class SchedulerError(Exception):
    """Base class for all scheduler errors."""


class ConflictError(SchedulerError):
    """An attendee would be in two overlapping events."""


class UnknownEvent(SchedulerError):
    """No event with this id exists."""
