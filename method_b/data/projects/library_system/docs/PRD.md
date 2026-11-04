# Product Requirements Document: Library Lending System

## 1. Overview
A small Python library (package `library`) that a community library uses to manage its
book catalogue, members, loans, overdue fines and simple reports. There is no user
interface and no database: everything is held in memory and used from Python code.

## 2. Goals
- Keep track of which books the library owns and how many copies are available.
- Let registered members borrow and return books, within a loan limit.
- Charge fines for late returns, according to a configurable fine policy.
- Produce an overdue report and a per-member summary for the front desk.

## 3. Constraints
- Python 3.12, standard library only (no third-party packages).
- Dates are `datetime.date` objects. The caller always passes "today" explicitly; the
  code never reads the system clock.
- Money amounts are `float` values rounded to 2 decimal places.

## 4. Functional requirements

### 4.1 Errors (`library/errors.py`)
All errors raised by the package derive from `LibraryError`:
`UnknownBook`, `UnknownMember`, `BookUnavailable`, `LoanLimitExceeded`, `NotOnLoan`.

### 4.2 Data model (`library/models.py`)
- **Book**: `isbn` (str), `title` (str), `author` (str), `year` (int), `copies` (int, default 1).
- **Member**: `member_id` (str), `name` (str), `email` (str), `max_loans` (int, default 3).
- **Loan**: `isbn`, `member_id`, `loan_date`, `due_date`, `returned_date` (default `None`).
  - `is_returned()` is True once `returned_date` is set.
  - `days_overdue(today)`: number of days between `due_date` and the return date (or
    `today` if not yet returned); never negative. Returning on the due date is 0 days.
  - `is_overdue(today)`: True only for a loan that is **not** returned and whose
    `due_date` is before `today`.

### 4.3 Catalogue (`library/catalog.py`)
`Catalog` stores books by ISBN and tracks available copies.
- `add_book(book)`: adds a book with all its copies available. Adding a book whose ISBN
  already exists increases the stored `Book`'s `copies` attribute by `book.copies` (so
  `get(isbn).copies` is the new total) and makes the added copies available.
- `get(isbn)` returns the `Book`; unknown ISBN → `UnknownBook`.
- `remove_book(isbn)`: unknown → `UnknownBook`; if any copy is on loan → `BookUnavailable`.
- `search(query)`: books whose title **or** author contains `query`, case-insensitive,
  sorted by title.
- `available_copies(isbn)`: unknown → `UnknownBook`.
- `take_copy(isbn)`: makes one copy unavailable; unknown → `UnknownBook`; no copy
  available → `BookUnavailable`.
- `return_copy(isbn)`: makes one copy available again (never more than `copies`).

### 4.4 Fines (`library/fines.py`)
`FinePolicy(daily_rate=0.25, grace_days=0, max_fine=10.0)`.
- `fine_for(loan, today)`: chargeable days = `loan.days_overdue(today) - grace_days`.
  If that is ≤ 0 the fine is `0.0`; otherwise `chargeable_days * daily_rate`, capped at
  `max_fine`, rounded to 2 decimals.

### 4.5 Loans (`library/loans.py`)
`LoanService(catalog, fine_policy=None, loan_period_days=14)`. If no policy is given a
default `FinePolicy()` is used. `catalog` and `fine_policy` are public attributes.
- `register_member(member)`: a second member with the same `member_id` → `LibraryError`.
- `get_member(member_id)`: unknown → `UnknownMember`.
- `checkout(member_id, isbn, today)` → `Loan`:
  - unknown member → `UnknownMember`;
  - member already has `max_loans` active (not returned) loans → `LoanLimitExceeded`;
  - takes a copy from the catalogue (which may raise `UnknownBook` / `BookUnavailable`);
  - `loan_date = today`, `due_date = today + loan_period_days`.
- `return_book(member_id, isbn, today)` → fine (float):
  - no active loan of that ISBN for that member → `NotOnLoan`;
  - marks the loan returned on `today`, returns the copy to the catalogue, computes the
    fine with the fine policy, adds it to the member's balance and returns it.
- `active_loans(member_id)`: the member's loans that are not returned, in checkout order.
- `overdue_loans(today)`: all overdue loans of all members, sorted by `due_date`
  (ties keep checkout order).
- `balance(member_id)`: unpaid fines of the member (0.0 initially).
- `pay(member_id, amount)` → remaining balance: `amount` must be > 0, otherwise
  `ValueError`. Paying more than the balance sets the balance to 0.0 (no credit).

### 4.6 Reports (`library/reports.py`)
- `overdue_report(service, today)` → list of strings, one per overdue loan, in the order
  of `service.overdue_loans(today)`, formatted exactly as
  `"<member name> | <book title> | <N> days | <fine with 2 decimals>"`, where the fine is
  what the member would be charged if the book were returned today,
  e.g. `"Ada Lovelace | Dune | 3 days | 0.75"`.
- `member_summary(service, member_id, today)` → dict with keys `member_id`, `name`,
  `active_loans` (count), `overdue` (count of overdue active loans), `balance` (unpaid
  fines) and `accrued_fines` (sum of the fines the overdue active loans would cost if
  returned today, rounded to 2 decimals).

## 5. Non-functional requirements
- Readable, maintainable code: each module has one clear responsibility.
- No global state; several `Catalog`/`LoanService` instances must be independent.
