# gymdesk

In-memory back office for a small gym: members and plans, trainers, weekly class
scheduling, bookings with e-mail notifications, monthly fees and payments, and a monthly
management report. Python 3.12, standard library only.

```
gymdesk/
  models.py         data records: Member, Trainer, GymClass, Booking, Payment
  timeslot.py       TimeSlot: half-open time ranges
  scheduling.py     Scheduler.plan_week: validates a week's proposed classes
  club.py           GymClub: the club's members, classes, bookings, fees and exports
  billing.py        plan prices, invoice totals, late fees
  notifications.py  booking / cancellation e-mails
  reports.py        MonthlyReport
  stats.py          attendance statistics
  checkin.py        CheckInDesk and e-mail helpers for the front desk
unit_tests/         pytest suite (20 tests)
docs/UML_class.md   class diagram
```

Run the tests: `python -m pytest unit_tests -q` from this directory.
