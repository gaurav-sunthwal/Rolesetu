"""Finds when an interview is, from the mail that announces it.

Best source first: the calendar invite attached to the mail, which states the
time exactly. Otherwise the wording ("Monday, 14 October at 3:00 PM IST").
When nothing certain is found, nothing is returned and the user is asked to
set the time themselves; a wrong time on a calendar is worse than none.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}  # fmt: skip
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTH = "|".join(sorted(_MONTHS, key=len, reverse=True))
# Offsets from UTC, in minutes, for the abbreviations mails actually use.
_ZONES = {
    "ist": 330, "utc": 0, "gmt": 0, "bst": 60, "cet": 60, "cest": 120, "est": -300, "edt": -240,
    "cst": -360, "cdt": -300, "pst": -480, "pdt": -420, "sgt": 480, "gst": 240, "aest": 600,
}  # fmt: skip

_DATES = (
    # 14 October 2026, 14th Oct
    re.compile(
        rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s+(?P<m>{_MONTH})\b\.?,?\s*(?P<y>\d{{4}})?",
        re.I,
    ),
    # October 14, 2026
    re.compile(
        rf"\b(?P<m>{_MONTH})\b\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b,?\s*(?P<y>\d{{4}})?", re.I
    ),
    # 2026-10-14
    re.compile(r"\b(?P<y>\d{4})-(?P<mn>\d{2})-(?P<d>\d{2})\b"),
    # 14/10/2026 (day first, as written in India and most of the world)
    re.compile(r"\b(?P<d>\d{1,2})[/-](?P<mn>\d{1,2})[/-](?P<y>\d{4}|\d{2})\b"),
)
_RELATIVE = re.compile(
    rf"\b(?P<word>today|tomorrow|day after tomorrow)\b|"
    rf"\b(?:on|this|coming|next)\s+(?P<weekday>{'|'.join(_WEEKDAYS)})\b",
    re.I,
)
_TIME = re.compile(
    r"\b(?P<h>\d{1,2})(?:[:.](?P<min>\d{2}))?\s*(?P<ap>[ap])\.?m\b\.?|"
    r"\b(?P<h24>[01]?\d|2[0-3]):(?P<min24>[0-5]\d)\b(?!\s*[ap]\.?m)",
    re.I,
)
_ZONE = re.compile(rf"\b({'|'.join(_ZONES)})\b", re.I)
_MEETING = re.compile(
    r"https?://(?:[\w.-]*\.)?(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com|"
    r"teams\.live\.com|webex\.com|whereby\.com|calendly\.com|cal\.com|"
    r"gotomeeting\.com|skype\.com)/[^\s<>\"')\]]+",
    re.I,
)
# How long an interview is assumed to last when the mail gives only a start.
DEFAULT_LENGTH = timedelta(minutes=45)
_LOOK_AHEAD = timedelta(days=120)


@dataclass(frozen=True)
class Schedule:
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    # False when only the day is known; `starts_at` is then midnight UTC of that day.
    has_time: bool = False
    link: str | None = None
    location: str | None = None


def _from_invite(calendar: str) -> Schedule | None:
    """Reads a calendar invite (.ics). Only the fields needed are looked at."""
    unfolded = re.sub(r"\r?\n[ \t]", "", calendar)

    def field(name: str) -> tuple[str, str] | None:
        match = re.search(rf"^{name}((?:;[^:\n]*)?):(.*)$", unfolded, re.M | re.I)
        return (match.group(1), match.group(2).strip()) if match else None

    def moment(found: tuple[str, str] | None) -> tuple[datetime, bool] | None:
        if found is None:
            return None
        params, value = found
        if re.fullmatch(r"\d{8}", value):
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC), False
        match = re.fullmatch(r"(\d{8}T\d{6})(Z?)", value)
        if not match:
            return None
        naive = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S")
        zone_name = re.search(r"TZID=([^;:]+)", params, re.I)
        try:
            zone = ZoneInfo(zone_name.group(1).strip('"')) if zone_name else UTC
        except (ZoneInfoNotFoundError, ValueError):
            zone = UTC
        return naive.replace(tzinfo=UTC if match.group(2) else zone).astimezone(UTC), True

    start = moment(field("DTSTART"))
    if start is None:
        return None
    end = moment(field("DTEND"))
    place = field("LOCATION")
    text = place[1].replace("\\,", ",").replace("\\n", " ") if place else ""
    link = _MEETING.search(unfolded)
    return Schedule(
        starts_at=start[0],
        ends_at=end[0] if end else None,
        has_time=start[1],
        link=link.group(0) if link else None,
        location=text[:200] if text and not text.startswith("http") else None,
    )


def _day(match: re.Match[str], sent: date) -> date | None:
    parts = match.groupdict()
    month = _MONTHS.get((parts.get("m") or "").lower()) or int(parts.get("mn") or 0)
    year = int(parts["y"]) if parts.get("y") else sent.year
    if year < 100:
        year += 2000
    try:
        found = date(year, month, int(parts["d"]))
    except ValueError:
        return None
    # "14 October" with no year, read in December, means next October.
    if not parts.get("y") and found < sent - timedelta(days=30):
        found = found.replace(year=year + 1)
    return found


def _relative_day(match: re.Match[str], sent: date) -> date:
    word = (match.group("word") or "").lower()
    if word:
        return sent + timedelta(days={"today": 0, "tomorrow": 1}.get(word, 2))
    ahead = (_WEEKDAYS.index(match.group("weekday").lower()) - sent.weekday()) % 7
    return sent + timedelta(days=ahead or 7)


def _clock(match: re.Match[str]) -> tuple[int, int] | None:
    if match.group("h24") is not None:
        return int(match.group("h24")), int(match.group("min24"))
    hour, minute = int(match.group("h")), int(match.group("min") or 0)
    if not 1 <= hour <= 12 or minute > 59:
        return None
    return hour % 12 + (12 if match.group("ap").lower() == "p" else 0), minute


def find_schedule(
    text: str, *, sent_at: datetime, sender_offset_minutes: int, calendar: str | None = None
) -> Schedule:
    """When the interview is, as far as the mail says. `sender_offset_minutes`
    is the sender's own timezone, used when the mail names none.
    """
    link_match = _MEETING.search(text)
    link = link_match.group(0).rstrip(".,;") if link_match else None
    if calendar:
        invite = _from_invite(calendar)
        if invite is not None:
            return Schedule(
                invite.starts_at, invite.ends_at, invite.has_time, invite.link or link,
                invite.location,
            )  # fmt: skip

    local_sent = (sent_at + timedelta(minutes=sender_offset_minutes)).date()
    candidates: list[tuple[int, int, date]] = []
    for pattern in _DATES:
        for match in pattern.finditer(text):
            day = _day(match, local_sent)
            if day is not None:
                candidates.append((match.start(), match.end(), day))
    for match in _RELATIVE.finditer(text):
        candidates.append((match.start(), match.end(), _relative_day(match, local_sent)))
    # The first date that is not in the past and not absurdly far away.
    upcoming = sorted(
        item for item in candidates if local_sent <= item[2] <= local_sent + _LOOK_AHEAD
    )
    if not upcoming:
        return Schedule(link=link)
    start, end, day = upcoming[0]

    # The time belongs to the date it sits beside: just after it, or just before.
    nearby = [(match.start() + end, match) for match in _TIME.finditer(text[end : end + 90])] or [
        (match.start() + max(0, start - 60), match)
        for match in _TIME.finditer(text[max(0, start - 60) : start])
    ]
    clocks = [(position, _clock(match), match) for position, match in nearby]
    clocks = [item for item in clocks if item[1] is not None]
    if not clocks:
        midnight = datetime(day.year, day.month, day.day, tzinfo=UTC)
        return Schedule(starts_at=midnight, has_time=False, link=link)

    position, clock, first = clocks[0]
    assert clock is not None
    zone_text = _ZONE.search(text[position : position + 60])
    offset = _ZONES[zone_text.group(1).lower()] if zone_text else sender_offset_minutes
    zone = timezone(timedelta(minutes=offset))
    starts = datetime(day.year, day.month, day.day, clock[0], clock[1], tzinfo=zone)

    ends: datetime | None = None
    if len(clocks) > 1 and re.search(
        r"^\s*(?:-|–|—|to|till|until)\s*$",
        text[first.end() + position - first.start() : clocks[1][0]],
    ):
        second = clocks[1][1]
        assert second is not None
        ends = datetime(day.year, day.month, day.day, second[0], second[1], tzinfo=zone)
        if ends <= starts:
            ends = None
    return Schedule(
        starts_at=starts.astimezone(UTC),
        ends_at=ends.astimezone(UTC) if ends else None,
        has_time=True,
        link=link,
    )
