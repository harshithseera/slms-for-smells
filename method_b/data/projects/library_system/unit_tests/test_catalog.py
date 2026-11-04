import pytest

from library.catalog import Catalog
from library.errors import BookUnavailable, LibraryError, UnknownBook
from library.models import Book

from conftest import DUNE, EMMA


def test_add_and_get(catalog):
    assert catalog.get(DUNE).title == "Dune"
    assert catalog.available_copies(DUNE) == 2


def test_adding_existing_isbn_adds_copies(catalog):
    catalog.add_book(Book(DUNE, "Dune", "Frank Herbert", 1965, copies=3))
    assert catalog.get(DUNE).copies == 5
    assert catalog.available_copies(DUNE) == 5


def test_unknown_isbn():
    with pytest.raises(UnknownBook):
        Catalog().get("nope")
    with pytest.raises(LibraryError):
        Catalog().available_copies("nope")


def test_search_is_case_insensitive_on_title_and_author_sorted_by_title(catalog):
    catalog.add_book(Book("1", "Children of Dune", "Frank Herbert", 1976))
    assert [b.title for b in catalog.search("HERBERT")] == ["Children of Dune", "Dune"]
    assert [b.title for b in catalog.search("emm")] == ["Emma"]
    assert catalog.search("tolkien") == []


def test_take_and_return_copy(catalog):
    catalog.take_copy(EMMA)
    assert catalog.available_copies(EMMA) == 0
    with pytest.raises(BookUnavailable):
        catalog.take_copy(EMMA)
    catalog.return_copy(EMMA)
    catalog.return_copy(EMMA)
    assert catalog.available_copies(EMMA) == 1


def test_remove_book(catalog):
    catalog.take_copy(DUNE)
    with pytest.raises(BookUnavailable):
        catalog.remove_book(DUNE)
    catalog.remove_book(EMMA)
    with pytest.raises(UnknownBook):
        catalog.get(EMMA)
