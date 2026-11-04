from datetime import date

import pytest

from library.catalog import Catalog
from library.loans import LoanService
from library.models import Book, Member

DUNE = "978-0441013593"
EMMA = "978-0141439587"
D0 = date(2026, 1, 1)


@pytest.fixture
def catalog():
    c = Catalog()
    c.add_book(Book(DUNE, "Dune", "Frank Herbert", 1965, copies=2))
    c.add_book(Book(EMMA, "Emma", "Jane Austen", 1815))
    return c


@pytest.fixture
def service(catalog):
    s = LoanService(catalog)
    s.register_member(Member("m1", "Ada Lovelace", "ada@example.org"))
    s.register_member(Member("m2", "Alan Turing", "alan@example.org", max_loans=1))
    return s
