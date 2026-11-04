"""The book catalogue and copy availability."""
from __future__ import annotations

from library.errors import BookUnavailable, UnknownBook
from library.models import Book


class Catalog:
    def __init__(self) -> None:
        self._books: dict[str, Book] = {}
        self._available: dict[str, int] = {}

    def add_book(self, book: Book) -> None:
        if book.isbn in self._books:
            self._books[book.isbn].copies += book.copies
            self._available[book.isbn] += book.copies
        else:
            self._books[book.isbn] = book
            self._available[book.isbn] = book.copies

    def get(self, isbn: str) -> Book:
        try:
            return self._books[isbn]
        except KeyError:
            raise UnknownBook(isbn) from None

    def remove_book(self, isbn: str) -> None:
        book = self.get(isbn)
        if self._available[isbn] < book.copies:
            raise BookUnavailable(f"{isbn} has copies on loan")
        del self._books[isbn]
        del self._available[isbn]

    def search(self, query: str) -> list[Book]:
        q = query.lower()
        hits = [b for b in self._books.values() if q in b.title.lower() or q in b.author.lower()]
        return sorted(hits, key=lambda b: b.title)

    def available_copies(self, isbn: str) -> int:
        self.get(isbn)
        return self._available[isbn]

    def take_copy(self, isbn: str) -> None:
        if self.available_copies(isbn) == 0:
            raise BookUnavailable(isbn)
        self._available[isbn] -= 1

    def return_copy(self, isbn: str) -> None:
        book = self.get(isbn)
        self._available[isbn] = min(book.copies, self._available[isbn] + 1)
