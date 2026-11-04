from scheduler.export import to_csv, to_ics

from helpers import at, ev


def events():
    return [ev("b", at(11), at(12), ["ana", "ben"], "Review"), ev("a", at(9), at(9, 30), [], "Focus")]


def test_csv():
    assert to_csv(events()) == "\n".join([
        "id,title,start,end,attendees",
        "a,Focus,2026-03-02 09:00,2026-03-02 09:30,",
        "b,Review,2026-03-02 11:00,2026-03-02 12:00,ana;ben",
    ])


def test_ics():
    assert to_ics(events()) == "\n".join([
        "BEGIN:VCALENDAR",
        "BEGIN:VEVENT", "UID:a", "SUMMARY:Focus", "DTSTART:20260302T090000", "DTEND:20260302T093000", "END:VEVENT",
        "BEGIN:VEVENT", "UID:b", "SUMMARY:Review", "DTSTART:20260302T110000", "DTEND:20260302T120000",
        "ATTENDEE:ana", "ATTENDEE:ben", "END:VEVENT",
        "END:VCALENDAR",
    ])


def test_empty():
    assert to_csv([]) == "id,title,start,end,attendees"
    assert to_ics([]) == "BEGIN:VCALENDAR\nEND:VCALENDAR"
