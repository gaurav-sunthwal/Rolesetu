"""Turns a company's source (which platform, and its settings) into a reader."""

from collections.abc import Callable, Mapping

from backend.modules.career_jobs.sources.base import Reader
from backend.modules.career_jobs.sources.boards import Ashby, Greenhouse, Lever, SmartRecruiters
from backend.modules.career_jobs.sources.enterprise import (
    Eightfold,
    OracleRecruiting,
    SuccessFactors,
)
from backend.modules.career_jobs.sources.own_sites import IBM, Amazon, Atlassian, Capgemini, Google
from backend.modules.career_jobs.sources.workday import Workday

_READERS: dict[str, Callable[..., Reader]] = {
    "workday": Workday,
    "greenhouse": Greenhouse,
    "lever": Lever,
    "ashby": Ashby,
    "smartrecruiters": SmartRecruiters,
    "eightfold": Eightfold,
    "successfactors": SuccessFactors,
    "oracle": OracleRecruiting,
    "amazon": Amazon,
    "ibm": IBM,
    "capgemini": Capgemini,
    "google": Google,
    "atlassian": Atlassian,
}

KINDS = frozenset(_READERS)


def build_reader(kind: str, config: Mapping[str, str]) -> Reader:
    return _READERS[kind](**config)
