"""Prompts live in versioned files, not inline strings. Changing a prompt means
adding a new version file and bumping the constant that points at it, so every
stored result records which wording produced it.
"""

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def load_prompt(name: str, version: int) -> str:
    return (_DIR / f"{name}.v{version}.md").read_text(encoding="utf-8").strip()
