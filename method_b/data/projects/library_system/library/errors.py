"""Exceptions raised by the library package."""


class LibraryError(Exception):
    """Base class for all library errors."""


class UnknownBook(LibraryError):
    """No book with this ISBN is in the catalogue."""


class UnknownMember(LibraryError):
    """No member with this id is registered."""


class BookUnavailable(LibraryError):
    """No copy of the book can be lent or removed right now."""


class LoanLimitExceeded(LibraryError):
    """The member already has the maximum number of active loans."""


class NotOnLoan(LibraryError):
    """The member has no active loan of this book."""
