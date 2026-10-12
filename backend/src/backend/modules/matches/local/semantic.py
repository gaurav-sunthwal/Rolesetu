"""A second opinion by meaning, for skills the dictionary could not find.

An embedding model turns a piece of text into a list of numbers so that texts
with similar meaning end up close together. Here it compares a skill ("experience
with authentication") against each line of the profile ("Secured the API with
Firebase Auth") and reports the closest line.

It is used narrowly on purpose. Measured on real profiles, this kind of model is
right about 86% of the time, which is not good enough to decide a verdict alone.
With a strict cut-off it found two thirds of the skills a profile shows without
naming, and no false ones, so it is only allowed to lift a "missing" skill to
"partial", and it always shows the line it matched.

The model runs on this machine: no network call, no cost per check.
"""

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np

from backend.core.config import get_settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Cosine similarity a line must reach to count as support. Set above the highest
# false match seen in calibration (0.333), with a margin, favouring a missed
# match over a wrong one.
SUPPORT_THRESHOLD = 0.38
_MIN_LINE_LENGTH = 25
_CACHE_SIZE = 4000


@dataclass(frozen=True)
class Support:
    line_index: int
    similarity: float


class Matcher(Protocol):
    def best_support(self, skill: str, lines: list[str]) -> Support | None: ...


class EmbeddingMatcher:
    """Holds the model and a cache of vectors already computed."""

    def __init__(self) -> None:
        self._model: TextEmbedding | None = None
        self._lock = threading.Lock()
        self._vectors: OrderedDict[str, np.ndarray] = OrderedDict()

    @property
    def ready(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        """Loads the model (downloading it on first run). Safe to call twice."""
        # Imported here, not at the top: the library is heavy, and while the
        # feature is switched off it should cost nothing at all.
        from fastembed import TextEmbedding

        with self._lock:
            if self._model is None:
                self._model = TextEmbedding(
                    model_name=MODEL_NAME, cache_dir=get_settings().model_cache_dir
                )

    def _embed(self, texts: list[str]) -> np.ndarray:
        assert self._model is not None
        missing = [text for text in dict.fromkeys(texts) if text not in self._vectors]
        if missing:
            with self._lock:
                for text, vector in zip(missing, self._model.embed(missing), strict=True):
                    self._vectors[text] = vector / (np.linalg.norm(vector) or 1.0)
                while len(self._vectors) > _CACHE_SIZE:
                    self._vectors.popitem(last=False)
        return np.array([self._vectors[text] for text in texts])

    def best_support(self, skill: str, lines: list[str]) -> Support | None:
        if not self.ready or not lines:
            return None
        query = self._embed([f"experience with {skill}"])[0]
        similarities = self._embed(lines) @ query
        best = int(similarities.argmax())
        score = float(similarities[best])
        return Support(best, score) if score >= SUPPORT_THRESHOLD else None


_matcher = EmbeddingMatcher()


def get_matcher() -> EmbeddingMatcher | None:
    """The shared matcher once its model is loaded, otherwise None. Scoring never
    waits for the model: until it is ready, checks use the dictionary alone.
    """
    return _matcher if _matcher.ready else None


def warm_up() -> None:
    """Loads the model in the background at startup."""
    if not get_settings().semantic_matching:
        return
    try:
        _matcher.load()
        logger.info("Semantic matcher ready (%s)", MODEL_NAME)
    except Exception:
        # Without the model, scoring still works on the dictionary alone.
        logger.exception("Semantic matcher could not be loaded")


def usable_lines(text: str) -> list[str]:
    """The lines of a description worth comparing: real sentences, not fragments."""
    return [line.strip() for line in text.splitlines() if len(line.strip()) >= _MIN_LINE_LENGTH]
