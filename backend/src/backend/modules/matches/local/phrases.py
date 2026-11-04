"""Requirements the dictionary does not know, read from how postings ask for them.

"Knowledge of building automation systems" names a skill even when the
dictionary has never heard of it: postings ask for skills with a small set of
lead-ins ("experience with", "knowledge of", "proficiency in"), and what follows
is the skill. Those phrases become requirements of their own, judged by the
words they share with the profile (see `judge.ProfileIndex`).

Only the object of a lead-in is taken, never a whole sentence, and soft skills
("problem-solving", "communication") are left out: no profile can prove them,
so they would only drag every score down.
"""

import re

from backend.modules.matches.local.catalog import Mention, Skill

MAX_WORDS = 4

_LEAD = re.compile(
    r"\b(?:hands[- ]on experience|experience|knowledge|understanding|proficiency|expertise|"
    r"familiarity|background|exposure|grounding|fluency|skilled|proficient|experienced|"
    r"well[- ]versed|working knowledge|competence)\s+(?:in|with|of|on|using|to)\s+",
    re.IGNORECASE,
)
# Where the skill named after a lead-in stops.
_STOP = re.compile(
    r"[.;:()]|\s+(?:such as|including|like|e\.g\.?|for example|to|that|which|who|where|"
    r"in order|is|are|would|will|preferred|is a plus|a plus|across|within)\b",
    re.IGNORECASE,
)
_EXAMPLES = re.compile(r"\s+(?:such as|including|like|e\.g)", re.IGNORECASE)
_SPLIT = re.compile(
    r"\s*,\s*(?:and/or\s+|and\s+|or\s+)?|\s+(?:and/or|and|or)\s+|\s*/\s*|\s*&\s*",
    re.IGNORECASE,
)
_LEADING_FILLER = re.compile(
    r"^(?:a|an|the|any|some|basic|strong|solid|good|excellent|deep|working|practical|sound|"
    r"proven|demonstrated|thorough|general|advanced|relevant|various|different|modern|core|"
    r"key|hands[- ]on|in[- ]depth|extensive|prior|previous|professional|industry|"
    r"at least|one|more|of|in|with|using)\s+",
    re.IGNORECASE,
)
_TRAILING_FILLER = re.compile(
    r"\s+(?:principles|concepts|fundamentals|basics|skills|techniques|practices|"
    r"methodologies|methods|knowledge|experience|is required|required)$",
    re.IGNORECASE,
)
# A phrase with one of these in it is a clause, not the name of a skill.
_CLAUSE_WORDS = frozenset(
    {"on", "to", "for", "from", "that", "which", "with", "at", "by", "into", "your", "our",
     "their", "you", "we", "they", "will", "can", "be", "is", "are", "years", "year"}
)  # fmt: skip
# What nobody's profile can show, or what says nothing about the job.
_SOFT_OR_GENERIC = re.compile(
    r"problem[- ]solving|communication|teamwork|team ?player|teams?\b|leadership|passion|"
    r"attitude|interpersonal|analytical|self[- ]motivat|detail|time management|english|"
    r"written|verbal|collaborat|ownership|curiosity|learning|fast[- ]paced|environment|"
    r"stakeholders?\b|customers?\b|clients?\b|people|business|industry|domain|field|role|"
    r"^(?:programming languages?|languages?|tools?|technolog(?:y|ies)|frameworks?|"
    r"systems?|software|platforms?|projects?|products?|applications?|this|it|them|work|"
    r"similar|related|relevant|other)$",
    re.IGNORECASE,
)


def _clean(item: str) -> str:
    text = re.sub(r"\s+", " ", item).strip(" -–—'\"")
    while (trimmed := _LEADING_FILLER.sub("", text)) != text:
        text = trimmed
    return _TRAILING_FILLER.sub("", text).strip()


def _is_skill_name(text: str) -> bool:
    words = text.lower().split()
    if not 1 <= len(words) <= MAX_WORDS or not 3 <= len(text) <= 50:
        return False
    if any(word in _CLAUSE_WORDS for word in words) or re.search(r"\d", text):
        return False
    if not re.fullmatch(r"[A-Za-z][A-Za-z +#.'-]*", text):
        return False
    return _SOFT_OR_GENERIC.search(text) is None


def find_phrases(sentence: str, mentions: list[Mention]) -> list[Skill]:
    """Skills named after a lead-in in this sentence that the dictionary did not
    already find there.
    """
    found: list[Skill] = []
    for lead in _LEAD.finditer(sentence):
        rest = sentence[lead.end() :]
        stop = _STOP.search(rest)
        obj = rest[: stop.start()] if stop else rest
        # "a cloud provider such as AWS or GCP": the words before the examples
        # only name their kind, and the examples are already requirements.
        if stop and _EXAMPLES.match(stop.group(0)):
            after = lead.end() + stop.end()
            if any(mention.start >= after for mention in mentions):
                continue
        start = lead.end()
        for raw in _SPLIT.split(obj):
            offset = sentence.find(raw, start) if raw else -1
            if offset >= 0:
                start = offset + len(raw)
            # A dictionary skill in this stretch was already taken as it is.
            if offset >= 0 and any(
                offset < mention.end and mention.start < offset + len(raw) for mention in mentions
            ):
                continue
            name = _clean(raw)
            if _is_skill_name(name):
                found.append(Skill(name=name[0].upper() + name[1:], phrase=True))
    return found
