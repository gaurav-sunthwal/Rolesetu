"""Word lists the section parsers use to tell a job title from a company, a
school from a degree, and a place from anything else.
"""

import re

_TITLE_WORDS = (
    "engineer", "developer", "intern", "internship", "manager", "analyst", "designer",
    "architect", "consultant", "lead", "head", "director", "officer", "scientist",
    "specialist", "associate", "administrator", "executive", "founder", "cofounder",
    "co-founder", "trainee", "programmer", "tester", "sde", "swe", "freelancer", "freelance",
    "researcher", "assistant", "teacher", "instructor", "lecturer", "professor", "tutor",
    "coordinator", "president", "cto", "ceo", "coo", "cfo", "contributor", "writer", "editor",
    "marketer", "recruiter", "representative", "technician", "accountant", "advisor",
    "owner", "devops", "sre", "strategist", "supervisor", "fellow", "apprentice",
    "ambassador", "volunteer", "mentor", "maintainer", "auditor", "operator", "planner",
    "producer", "nurse", "doctor", "physician", "attorney", "lawyer", "paralegal", "partner",
    "principal", "staff", "member", "captain", "secretary", "treasurer", "organizer",
    "organiser", "evangelist", "practitioner", "generalist", "qa",
)  # fmt: skip
_TITLE = re.compile(rf"(?<![\w-])(?:{'|'.join(_TITLE_WORDS)})s?(?![\w-])", re.IGNORECASE)

_COMPANY = re.compile(
    r"(?<!\w)(?:inc|ltd|limited|llc|llp|pvt|private|corp|corporation|co|company|gmbh|plc|"
    r"technologies|technology|solutions|labs|systems|software|services|consulting|"
    r"consultancy|group|ventures|studio|studios|enterprises|industries|bank|university|"
    r"institute|college|foundation|agency|networks|global|international|digital|media|"
    r"analytics|motors|traders|partners|holdings|startup)(?!\w)",
    re.IGNORECASE,
)

_SCHOOL = re.compile(
    r"(?<!\w)(?:university|universit\w+|institute|college|school|academy|polytechnic|"
    r"vidyalaya|vidyapeeth|vidyapith|iit|nit|iiit|bits|iim|iisc|mit)(?!\w)",
    re.IGNORECASE,
)

# Longest alternatives first, so "Bachelor of Engineering" wins over "B.E".
_DEGREE = re.compile(
    r"(?<![\w.])(?:"
    r"(?:bachelor|master|doctor|associate)(?:'?s)?(?:\s+degree)?(?:\s+(?:of|in)\s+[A-Za-z]+(?:\s+(?:and|&)\s+[A-Za-z]+)?)?"
    r"|post\s*graduate\s+diploma|pg\s+diploma|diploma|"
    r"b\.?\s?tech|m\.?\s?tech|b\.?\s?sc|m\.?\s?sc|b\.?\s?com|m\.?\s?com|b\.?\s?ca|m\.?\s?ca|"
    r"b\.?\s?ba|m\.?\s?ba|b\.?\s?arch|b\.?\s?des|m\.?\s?des|b\.?\s?ed|m\.?\s?ed|ll\.?\s?b|ll\.?\s?m|"
    r"ph\.?\s?d|m\.?\s?phil|b\.?\s?e|m\.?\s?e|b\.?\s?s|m\.?\s?s|b\.?\s?a|m\.?\s?a|"
    r"higher\s+secondary(?:\s+certificate)?|senior\s+secondary|secondary\s+school(?:\s+certificate)?|"
    r"high\s+school(?:\s+diploma)?|intermediate|hsc|ssc|cbse|icse|"
    r"class\s+(?:xii|x|12|10)(?:th)?|12th|10th|xii|matriculation"
    r")(?![\w])\.?",
    re.IGNORECASE,
)

PLACES = frozenset(
    [
        "india",
        "usa",
        "us",
        "uk",
        "canada",
        "australia",
        "germany",
        "france",
        "singapore",
        "uae",
        "netherlands",
        "ireland",
        "japan",
        "china",
        "brazil",
        "spain",
        "italy",
        "sweden",
        "switzerland",
        "poland",
        "nepal",
        "bangladesh",
        "pakistan",
        "srilanka",
        "indonesia",
        "malaysia",
        "philippines",
        "vietnam",
        "nigeria",
        "kenya",
        "egypt",
        "mexico",
        "argentina",
        "portugal",
        "remote",
        "hybrid",
        "onsite",
        "on-site",
        "bengaluru",
        "bangalore",
        "mumbai",
        "delhi",
        "gurgaon",
        "gurugram",
        "noida",
        "hyderabad",
        "chennai",
        "pune",
        "kolkata",
        "ahmedabad",
        "jaipur",
        "lucknow",
        "indore",
        "bhopal",
        "chandigarh",
        "kochi",
        "coimbatore",
        "nagpur",
        "surat",
        "vadodara",
        "thiruvananthapuram",
        "mysuru",
        "mysore",
        "visakhapatnam",
        "patna",
        "bhubaneswar",
        "guwahati",
        "dehradun",
        "mangalore",
        "nashik",
        "rajkot",
        "maharashtra",
        "karnataka",
        "telangana",
        "gujarat",
        "rajasthan",
        "kerala",
        "punjab",
        "haryana",
        "bihar",
        "odisha",
        "assam",
        "goa",
        "uttarakhand",
        "jharkhand",
        "chhattisgarh",
        "london",
        "manchester",
        "dublin",
        "berlin",
        "munich",
        "paris",
        "amsterdam",
        "toronto",
        "vancouver",
        "sydney",
        "melbourne",
        "dubai",
        "tokyo",
        "boston",
        "seattle",
        "austin",
        "chicago",
        "denver",
        "atlanta",
        "ca",
        "ny",
        "tx",
        "wa",
        "ma",
        "il",
        "nj",
        "fl",
        "pa",
        "va",
        "ga",
        "co",
        "nc",
        "oh",
        "mi",
        "az",
        "california",
        "texas",
        "washington",
        "massachusetts",
        "illinois",
        "florida",
        "virginia",
        "georgia",
        "colorado",
    ]
)


def has_title_word(text: str) -> bool:
    return bool(_TITLE.search(text))


def has_company_word(text: str) -> bool:
    return bool(_COMPANY.search(text))


def has_school_word(text: str) -> bool:
    return bool(_SCHOOL.search(text))


def find_degree(text: str) -> re.Match[str] | None:
    return _DEGREE.search(text)


def is_place(text: str) -> bool:
    """True for "Pune", "Bengaluru, India", "Remote", "San Francisco, CA"."""
    if not text or len(text) > 45 or any(char.isdigit() for char in text):
        return False
    words = [
        word.strip(".,()").lower() for word in re.split(r"[\s,/]+", text) if word.strip(".,()")
    ]
    if not words or len(words) > 5:
        return False
    return words[-1] in PLACES or (len(words) <= 2 and words[0] in PLACES)
