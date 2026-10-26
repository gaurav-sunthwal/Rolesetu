"""Which Indian cities a job's location names.

Careers sites spell places their own way ("Bangalore", "Bengaluru, KA, IN",
"IND-29, Bengaluru"), so a job is filed under one name per city, the one the
city filter shows.
"""

import re

# The city's name in the filter, then every spelling sites use for it.
_CITIES: dict[str, tuple[str, ...]] = {
    "Bengaluru": ("bengaluru", "bangalore", "bengalore"),
    "Hyderabad": ("hyderabad", "secunderabad"),
    "Pune": ("pune",),
    "Chennai": ("chennai", "madras"),
    "Mumbai": ("mumbai", "bombay"),
    "Navi Mumbai": ("navi mumbai",),
    "Gurugram": ("gurugram", "gurgaon"),
    "Noida": ("noida",),
    "Delhi": ("new delhi", "delhi"),
    "Kolkata": ("kolkata", "calcutta"),
    "Ahmedabad": ("ahmedabad",),
    "Gandhinagar": ("gandhinagar", "gift city"),
    "Jaipur": ("jaipur",),
    "Coimbatore": ("coimbatore",),
    "Kochi": ("kochi", "cochin"),
    "Thiruvananthapuram": ("thiruvananthapuram", "trivandrum"),
    "Chandigarh": ("chandigarh",),
    "Mohali": ("mohali",),
    "Indore": ("indore",),
    "Nagpur": ("nagpur",),
    "Bhubaneswar": ("bhubaneswar",),
    "Mysuru": ("mysuru", "mysore"),
    "Mangaluru": ("mangaluru", "mangalore"),
    "Vadodara": ("vadodara", "baroda"),
    "Lucknow": ("lucknow",),
    "Visakhapatnam": ("visakhapatnam", "vizag"),
    "Bhopal": ("bhopal",),
    "Surat": ("surat",),
}
_SPELLINGS = sorted(
    ((spelling, city) for city, names in _CITIES.items() for spelling in names),
    key=lambda pair: -len(pair[0]),
)
_PATTERN = re.compile(r"\b(" + "|".join(re.escape(s) for s, _ in _SPELLINGS) + r")\b", re.I)
_CITY_OF = dict(_SPELLINGS)
# Not the two-letter "IN": that is also Indiana ("Indianapolis, IN").
_COUNTRY = re.compile(r"(?i:\bindia\b)|(?:^|[,\s-])IND(?:$|[,\s-])")

CITIES = tuple(_CITIES)


def cities_in(location: str) -> list[str]:
    """The cities named, each once, in the order they appear."""
    found: list[str] = []
    text = location.lower()
    position = 0
    while match := _PATTERN.search(text, position):
        city = _CITY_OF[match.group(1).lower()]
        # "Navi Mumbai" is its own city, not also Mumbai.
        if city not in found:
            found.append(city)
        position = match.end()
    return found


def is_india(location: str) -> bool:
    return bool(_COUNTRY.search(location) or _PATTERN.search(location))


REMOTE = "Remote"
OTHER = "Other places in India"


def filter_places(location: str) -> list[str]:
    """What the city filter files a job under: its cities, "Remote", or, when
    the site names no city we know, a catch-all so the job is never lost."""
    places = cities_in(location)
    if re.search(r"\bremote\b|work from home|\bwfh\b", location, re.I):
        places.append(REMOTE)
    return places or [OTHER]
