# Architecture Design

File tree:
```bash
├── library
│   ├── __init__.py
│   ├── errors.py
│   ├── models.py
│   ├── catalog.py
│   ├── fines.py
│   ├── loans.py
│   └── reports.py
```

Dependencies between modules (lower layers never import higher ones):
`errors` ← `models` ← `catalog`, `fines` ← `loans` ← `reports`.

`errors.py`
- `LibraryError(Exception)` and its subclasses `UnknownBook`, `UnknownMember`,
  `BookUnavailable`, `LoanLimitExceeded`, `NotOnLoan`.

`models.py`
- `Book`, `Member`, `Loan` (dataclasses). `Loan.is_returned()`, `Loan.days_overdue(today)`,
  `Loan.is_overdue(today)`.

`catalog.py`
- `class Catalog()`: `add_book`, `get`, `remove_book`, `search`, `available_copies`,
  `take_copy`, `return_copy`.

`fines.py`
- `class FinePolicy(daily_rate=0.25, grace_days=0, max_fine=10.0)`: `fine_for(loan, today)`.

`loans.py`
- `class LoanService(catalog, fine_policy=None, loan_period_days=14)`: `register_member`,
  `get_member`, `checkout`, `return_book`, `active_loans`, `overdue_loans`, `balance`, `pay`.

`reports.py`
- `overdue_report(service, today)` and `member_summary(service, member_id, today)`
  (module-level functions).

Usage example:
```python
from datetime import date
from library.catalog import Catalog
from library.loans import LoanService
from library.models import Book, Member
from library.reports import overdue_report

cat = Catalog()
cat.add_book(Book("978-0441013593", "Dune", "Frank Herbert", 1965, copies=2))
svc = LoanService(cat)
svc.register_member(Member("m1", "Ada Lovelace", "ada@example.org"))
svc.checkout("m1", "978-0441013593", date(2026, 1, 1))
print(overdue_report(svc, date(2026, 1, 18)))   # ['Ada Lovelace | Dune | 3 days | 0.75']
```
