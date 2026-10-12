"""Reading when an interview is from the mail that announces it."""

from datetime import UTC, datetime

import pytest

from backend.modules.inbox.schedule import find_schedule

# A Monday, 11:30 in India.
SENT = datetime(2026, 10, 12, 6, 0, tzinfo=UTC)
INDIA = 330


def when(text: str, calendar: str | None = None) -> tuple[str | None, bool]:
    found = find_schedule(text, sent_at=SENT, sender_offset_minutes=INDIA, calendar=calendar)
    return (found.starts_at.strftime("%Y-%m-%d %H:%M") if found.starts_at else None, found.has_time)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Times are given in UTC: 3:00 PM IST is 09:30 UTC.
        ("Scheduled on Wednesday, 14 October 2026 at 3:00 PM IST.", ("2026-10-14 09:30", True)),
        ("Interview on 15th Oct, 11:30 AM - 12:15 PM.", ("2026-10-15 06:00", True)),
        ("Interview: October 16, 2026 14:00 on Zoom.", ("2026-10-16 08:30", True)),
        ("Date: 20/10/2026 Time: 2:30 PM", ("2026-10-20 09:00", True)),
        ("Please join the call tomorrow at 4 pm.", ("2026-10-13 10:30", True)),
        ("Your slot is on Friday at 10.30 AM IST", ("2026-10-16 05:00", True)),
        # A named timezone wins over the sender's own.
        ("Interview on 19 October 2026 at 5 PM EST.", ("2026-10-19 22:00", True)),
        # A date in the past is about something else; the next one is the interview.
        (
            "You applied on 2 October 2026. Interview on 19 October 2026 at 5 PM.",
            ("2026-10-19 11:30", True),
        ),
        # Only the day is known.
        ("The interview will be held on 22 October. Time to follow.", ("2026-10-22 00:00", False)),
        # Nothing certain: say nothing rather than guess.
        ("Please share your availability for an interview next week.", (None, False)),
        ("We look forward to speaking with you.", (None, False)),
    ],
)
def test_finds_the_date_and_time(text: str, expected: tuple[str | None, bool]) -> None:
    assert when(text) == expected


def test_an_end_time_is_read_from_a_range() -> None:
    found = find_schedule(
        "Interview on 15 Oct, 11:30 AM - 12:15 PM", sent_at=SENT, sender_offset_minutes=INDIA
    )
    assert found.ends_at is not None
    assert found.ends_at.strftime("%H:%M") == "06:45"


def test_finds_the_meeting_link_even_without_a_time() -> None:
    meet = find_schedule(
        "Join here: https://meet.google.com/abc-defg-hij.", sent_at=SENT, sender_offset_minutes=0
    )
    assert meet.link == "https://meet.google.com/abc-defg-hij"
    slot = find_schedule(
        "Pick a slot: https://calendly.com/acme-hr/30min", sent_at=SENT, sender_offset_minutes=0
    )
    assert (slot.starts_at, slot.link) == (None, "https://calendly.com/acme-hr/30min")


def test_a_calendar_invite_is_trusted_over_the_wording() -> None:
    invite = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
        "DTSTART;TZID=Asia/Kolkata:20261014T150000\r\n"
        "DTEND;TZID=Asia/Kolkata:20261014T154500\r\n"
        "LOCATION:Acme HQ\\, Pune\r\n"
        "DESCRIPTION:Join https://teams.microsoft.com/l/meetup-join/abc\r\n"
        "END:VEVENT\r\nEND:VCALENDAR"
    )
    found = find_schedule(
        "Interview tomorrow at 9 AM", sent_at=SENT, sender_offset_minutes=INDIA, calendar=invite
    )
    assert found.starts_at == datetime(2026, 10, 14, 9, 30, tzinfo=UTC)
    assert found.ends_at == datetime(2026, 10, 14, 10, 15, tzinfo=UTC)
    assert (found.has_time, found.location) == (True, "Acme HQ, Pune")
    assert found.link == "https://teams.microsoft.com/l/meetup-join/abc"

    utc_invite = "BEGIN:VEVENT\nDTSTART:20261014T093000Z\nEND:VEVENT"
    assert when("Invitation", utc_invite) == ("2026-10-14 09:30", True)
